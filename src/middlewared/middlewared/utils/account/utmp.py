# Various low-level functions related to utmp. These are blocking under a global lock due to
# thread-safety concerns.

import ctypes
import enum
import errno
import os
import struct

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
from middlewared.utils.nss.grp import getgrnam
from middlewared.utils.nss.pwd import getpwuid
from socket import ntohl
from threading import RLock  # Generally utmp operations are MT-UNSAFE and race prone


__all__ = [
    'iter_utent', 'utmp_query', 'wtmp_query', 'LoginFile', 'PyUtmpType', 'PyUtmpEntry',
    'PyUtmpExit', 'login', 'logout',
]

libc = ctypes.CDLL('libc.so.6', use_errno=True)
UTMP_LOCK = RLock()


def __ensure_login_file(path: str) -> None:
    # Ensure containing directory exists (e.g., /run or /var/log)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    fd = os.open(path, os.O_CREAT | os.O_APPEND, 0o664)
    os.close(fd)

    # Resolve utmp group if present; fall back to root
    try:
        gid = getgrnam('utmp', as_dict=True)['gr_gid']
    except KeyError:
        gid = 0

    # chown root:utmp (or root:root) and set explicit perms
    try:
        os.chown(path, 0, gid)
    except PermissionError:
        pass

    try:
        os.chmod(path, 0o664)
    except PermissionError:
        pass


class MiddlewareTTYName(enum.StrEnum):
    """ Names for the ut_id and ut_line fields """
    WEBSOCKET = 'ws'
    WEBSOCKET_SECURE = 'wss'
    WEBSOCKET_UNIX = 'wsu'


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

    def to_ctype(self):
        """ Convert dataclass into ctypes StructUtmp for login / logout calls """
        tv_sec = int(self.ut_tv.timestamp())
        ut_exit = self.ut_exit or PyUtmpExit(0, 0)
        # Pack up until address
        packed = struct.pack(
            f'hi{UT_LINESIZE}s4s{UT_NAMESIZE}s{UT_HOSTSIZE}shhiii',
            self.ut_type,
            self.ut_pid,
            self.ut_line.encode(),
            self.ut_id.encode(),
            self.ut_user.encode(),
            self.ut_host.encode(),
            ut_exit.e_termination,
            ut_exit.e_exit,
            self.ut_session,
            tv_sec,
            self.ut_tv.microsecond,
        )

        if isinstance(self.ut_addr, IPv4Address):
            packed += self.ut_addr.packed
            packed += struct.pack('iii', 0, 0, 0)

        else:
            packed += self.ut_addr.packed

        packed += struct.pack('20s', 20 * b'\x00')

        return StructUtmp.from_buffer_copy(packed)


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
        raise RuntimeError(f'utmpname() failed with error: {os.strerror(ctypes.get_errno())}')


def __getutent():
    # Read a line from the current position in the utmp file. We don't bother with
    # re-entrant versions because we're taking a global lock due to concerns about file position
    # struct utmp *getutent(void);
    func = libc.getutent
    func.argtypes = []
    func.restype = ctypes.c_void_p

    res = func()
    return ctypes.cast(res, ctypes.POINTER(StructUtmp))


def __pututline(entry: StructUtmp) -> None:
    # Write the utmp structure to the utmp file specified by prior __utmpname() call
    # struct utmp *pututline(const struct utmp *ut);
    func = libc.pututline
    func.argtypes = [ctypes.POINTER(StructUtmp)]
    func.restype = ctypes.c_void_p

    res = func(ctypes.byref(entry))
    if not res:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))

    return ctypes.cast(res, ctypes.POINTER(StructUtmp))


def __logout(ut_line: bytes) -> None:
    # Clear the specified utmp entry by zeroing out the ut_name and ut_host fields, updating
    # ut_tv (timestamp) and changing ut_type to DEAD_PROCESS. The changes are accomplished
    # via logout(3).
    func = libc.logout
    func.argtypes = [ctypes.c_char_p]
    func.restype = ctypes.c_int

    rv = func(ut_line)
    if rv == 0:
        # logout returns 1 on success and 0 on failure
        raise RuntimeError(f'logout() failed with error: {os.strerror(ctypes.get_errno())}')


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

    if not any(val for val in int_array[1:3]):
        # IPv4 Address only uses ut_addr_v6[0]
        try:
            return IPv4Address(ntohl(int_array[0]))
        except Exception:
            return None

    ipv6_val = ntohl(int_array[0]) << 96
    ipv6_val += ntohl(int_array[1]) << 64
    ipv6_val += ntohl(int_array[2]) << 32
    ipv6_val += ntohl(int_array[3])

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


def __pututline_file(file: LoginFile, entry: StructUtmp) -> None:
    try:
        return __pututline_file_impl(file, entry)
    except OSError as e:
        if e.errno == errno.ENOENT:
            __endutent()
            __ensure_login_file(str(file))
            return __pututline_file_impl(file, entry)
        raise


def __pututline_file_impl(file: LoginFile, entry: StructUtmp) -> None:
    # WARNING: this assumes global lock (UTMP_LOCK) already held
    __utmpname(file)
    __setutent()
    try:
        # Seek to current entry (if it exists) then insert
        while existing := __getutent():
            if existing.contents.ut_line == entry.ut_line:
                break

        __pututline(entry)
    finally:
        __endutent()

        if file != LoginFile.UTMP:
            __utmpname(LoginFile.UTMP)


def login(entry: PyUtmpEntry):
    """
    Create utmp and wtmp entries based on the specified entry.
    We are using putent(3) rather than login(3) because the latter tries to resolve to
    tty and will in the end only write to the wtmp file.
    """
    utmp_entry = entry.to_ctype()
    with UTMP_LOCK:
        __pututline_file(LoginFile.UTMP, utmp_entry)
        __pututline_file(LoginFile.WTMP, utmp_entry)


def logout(to_remove: PyUtmpEntry):
    """ Remove utmp entry and insert logout into wtmp """

    assert to_remove.ut_type == PyUtmpType.USER_PROCESS
    with UTMP_LOCK:
        __logout(to_remove.ut_line.encode())
