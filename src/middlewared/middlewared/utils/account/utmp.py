# Various low-level functions related to utmp. These are blocking under a global lock due to
# thread-safety concerns.

import ctypes
import enum

from .constants import (
    UT_LINESIZE,
    UT_NAMESIZE,
    UT_HOSTSIZE,
)

from dataclasses import asdict, dataclass
from datetime import datetime, UTC
from ipaddress import IPv4Address, IPv6Address
from middlewared.utils import filter_list
from middlewared.utils.auth import get_login_uid, AUID_UNSET, AUID_FAULTED
from middlewared.utils.nss.pwd import getpwuid
from socket import ntohl
from threading import Lock  # Generally utmp operations are MT-UNSAFE and race prone


libc = ctypes.CDLL('libc.so.6', use_errno=True)
UTMP_LOCK = Lock()

__all__ = ['iter_utent', 'utmp_query', 'LoginFile', 'PyUtmpType', 'PyUtmpEntry', 'PyUtmpExit']


class PyUtmpType(enum.IntEnum):
    EMPTY = 0  # Record does not contain valid info
    RUN_LVL = 1  # run level
    BOOT_TIME = 2  # time of system boot (in ut_tv)
    NEW_TIME = 3  # time after system clock change
    OLD_TIME = 4  # time before system clock change
    INIT_PROCESS = 5  # process spawned by init(8)
    LOGIN_PROCESS = 6  # session leader process for user login
    USER_PROCESS = 7  # normal process
    DEAD_PROCESS = 8  # terminated process
    ACCOUNTING = 9  # not implemented


class LoginFile(enum.StrEnum):
    UTMP = '/var/run/utmp'
    WTMP = '/var/log/wtmp'


class StructExitStatus(ctypes.Structure):
    _fields_ = [
        ('e_termination', ctypes.c_short),
        ('e_exit', ctypes.c_short),
    ]


class StructTimeval(ctypes.Structure):
    # This is currently using 32bit time, but may change to c_int64 for 2038 compat
    _fields_ = [
        ('tv_sec', ctypes.c_int32),
        ('tv_usec', ctypes.c_int32),
    ]


class StructUtmp(ctypes.Structure):
    _fields_ = [
        ('ut_type', ctypes.c_short),
        ('ut_pid', ctypes.c_int32),
        ('ut_line', ctypes.c_char * UT_LINESIZE),
        ('ut_id', ctypes.c_char * 4),
        ('ut_user', ctypes.c_char * UT_NAMESIZE),
        ('ut_host', ctypes.c_char * UT_HOSTSIZE),
        ('ut_exit', StructExitStatus),
        ('ut_session', ctypes.c_int32),  # This may become c_long for 2038 compat
        ('ut_tv', StructTimeval),
        ('ut_addr', ctypes.c_uint32 * 4),  # Despite header these are netlong
        ('__unused', ctypes.c_char * 20),
    ]


@dataclass(frozen=True)
class PyUtmpExit:
    """ python dataclass wrapping around StructExitStatus """
    e_termination: int  # Process termination status (short)
    e_exit: int  # Process exit status (short)


@dataclass(frozen=True)
class PyUtmpEntry:
    """ Python dataclass wrapping around struct utmp. C type information enclosed in parentheses """
    ut_type: PyUtmpType  # Type of record (short)
    ut_pid: int  # PID of login process (pid_t)
    ut_line: str  # Device name of tty - "/dev/" (char ut_line[UT_LINESIZE];)
    ut_id: str  # Terminal name suffix or inittab(5) ID (char ut_id[4];)
    ut_user: str  # Username (char ut_user[UT_NAMESIZE];)
    ut_host: str  # Hostname for remote login or kernel version for run-level messages (char ut_host[UT_HOSTSIZE])
    ut_exit: PyUtmpExit  # Exit status of process marked as DEAD_PROCESS
    ut_session: int  # Session ID (long)
    ut_tv: datetime  # Time entry was made (struct timeval)
    ut_addr: IPv4Address | IPv6Address  # IP address of remote host  (int32_t ut_addr_v6[4])


def __setutent():
    # Rewind the file pointer to beginning of utmp file
    # void setutent(void);
    func = libc.setutent
    func.argtypes = []
    func.restype = None
    func()


def __endutent():
    # Close the utmp file
    # void endutent(void);
    func = libc.endutent
    func.argtypes = []
    func.restype = None
    func()


def __utmpname(file: LoginFile):
    # Sets the name of the utmp-format file for other utmp file names to access
    func = libc.utmpname
    func.argtypes = [ctypes.c_char_p]
    func.restype = ctypes.c_int

    res = int(func(ctypes.c_char_p(str(file).encode())))
    if res != 0:
        raise RuntimeError(f'utmpname() failed with error: {ctypes.get_errno()}')


def __getutent():
    # Read a line from the current position in the utmp file. We don't bother with
    # re-entrant versions because we're taking a global lock due to concerns about file position
    # struct utmp *getutent(void);
    func = libc.getutent
    func.argtypes = []
    func.restype = ctypes.c_void_p

    res = func()
    return ctypes.cast(res, ctypes.POINTER(StructUtmp))


def __parse_utmp_exit(utmp_type: PyUtmpType, data: StructExitStatus) -> PyUtmpExit:
    if utmp_type != PyUtmpType.DEAD_PROCESS:
        # Per utmp(5) manpage the struct exit_status is only populated on DEAD_PROCESS
        # i.e. processes that have been terminated. This means we'll set it to None
        # type to differentiate from exit status of zero to prevent users from trying
        # to rely on it.
        return None

    return PyUtmpExit(e_termination=data.e_termination, e_exit=data.e_exit)


def __parse_timeval(data: StructTimeval) -> datetime:
    secs = data.tv_sec
    secs += (data.tv_usec / 1000000)
    if secs == 0:
        return None

    return datetime.fromtimestamp(secs, UTC)


def __parse_address(int_array) -> IPv4Address | IPv6Address | None:
    if not any(int_array):
        return None

    if not int_array[1]:
        # IPv4 Address only uses ut_addr_v6[0]
        try:
            return IPv4Address(ntohl(int_array[0]))
        except Exception:
            return None

    ipv6_val = ntohl(int_array[0])
    ipv6_val += ntohl(int_array[1]) << 32
    ipv6_val += ntohl(int_array[2]) << 64
    ipv6_val += ntohl(int_array[3]) << 96

    try:
        return IPv6Address(ipv6_val)
    except Exception:
        return None


def __parse_utmp_entry(entry: StructUtmp) -> PyUtmpEntry:
    # Convert our utmp buffer to python dataclass
    return PyUtmpEntry(
        ut_type=PyUtmpType(entry.contents.ut_type),
        ut_pid=entry.contents.ut_pid or None,
        ut_line=entry.contents.ut_line.decode() or None,
        ut_id=entry.contents.ut_id.decode(),
        ut_user=entry.contents.ut_user.decode() or None,
        ut_host=entry.contents.ut_host.decode() or None,
        ut_exit=__parse_utmp_exit(entry.contents.ut_type, entry.contents.ut_exit),
        ut_session=entry.contents.ut_session,
        ut_tv=__parse_timeval(entry.contents.ut_tv),
        ut_addr=__parse_address(entry.contents.ut_addr)
    )


def __extend_utmp_entry(entry: StructUtmp) -> dict:
    data = asdict(entry)
    if data['ut_type'] is PyUtmpType.USER_PROCESS:
        # Some NSS backends may provide usernames that are greater than 32 characters
        # in length. This means we should grab the loginuid for active processes and
        # get an authoritative password entry based on the actual process information.
        loginuid = get_login_uid(data['ut_pid'])

        # NOTE: if we were unusccessful in getting loginuid for process then set these to None
        # This can happen if process no longer exists, but utmp entry didn't get cleaned up
        data['loginuid'] = None if loginuid in (AUID_UNSET, AUID_FAULTED) else loginuid
        data['passwd'] = None if loginuid in (AUID_UNSET, AUID_FAULTED) else getpwuid(loginuid, as_dict=True)
    else:
        data['loginuid'] = None
        data['passwd'] = None

    # Put ut_type string for easier search API
    data['ut_type_str'] = data['ut_type'].name
    if data['ut_addr']:
        # Allow JSON serialization of the IP address
        data['ut_addr'] = data['ut_addr'].compressed

    return data


def iter_utent(file: LoginFile):
    # Iterate utmp entries under a threading lock. The glibc library handles fcntl locking
    # on the file and so we don't have to worry about inter-process concurrency.
    with UTMP_LOCK:
        __utmpname(file)
        __setutent()
        try:
            while utmp_entry := __getutent():
                yield __parse_utmp_entry(utmp_entry)
        finally:
            __endutent()


def __iter_expanded_utent(file: LoginFile):
    for entry in iter_utent(file):
        yield __extend_utmp_entry(entry)


def utmp_query(filters: list | None = None, options: dict | None = None) -> list:
    """ Use query-filters and query-options to iterate /var/run/utmp """
    return filter_list(__iter_expanded_utent(LoginFile.UTMP), filters or [], options or {})


def wtmp_query(filters: list | None = None, options: dict | None = None) -> list:
    """ Use query-filters and query-options to iterate /var/log/wtmp """
    return filter_list(__iter_expanded_utent(LoginFile.WTMP), filters or [], options or {})
