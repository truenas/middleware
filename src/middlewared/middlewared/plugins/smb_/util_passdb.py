# Utilities that wrap around samba's passdb.tdb file
#
# test coverage provided by src/middlewared/middlewared/pytest/unit/utils/test_passdb.py
# sample tdb contents (via tdbdump)
#
# {
# key(19) = "INFO/minor_version\00"
# data(4) = "\00\00\00\00"
# }
# {
# key(13) = "RID_00004e66\00"
# data(8) = "smbuser\00"
# }
# {
# key(9) = "NEXT_RID\00"
# data(4) = "\E9\03\00\00"
# }
# {
# key(13) = "USER_smbuser\00"
# data(202) = "\00\00\00\00\7F\A9T|\7F\A9T|\00\00\00\00z\91\C4f\00\00\00\00\7F\A9T|\08\00\00\00smbuser\00\0F\00\00\00TESTMJPYWOO8AG\00\01\00\00\00\00\08\00\00\00smbuser\00\00\00\00\00\00\00\00\00\00\00\00\00\00\00\00\00\01\00\00\00\00\01\00\00\00\00\01\00\00\00\00\01\00\00\00\00fN\00\00\01\02\00\00\00\00\00\00\10\00\00\00\B3\F3O\F0\FB\B7r\A1\A7\08\10\CB\B32\07@\00\00\00\00\10\00\00\00\A8\00\15\00\00\00 \00\00\00\FF\FF\FF\FF\FF\FF\FF\FF\FF\FF\FF\FF\FF\FF\FF\FF\FF\FF\FF\FF\FF\00\00\00\00\00\00\00\00\00\00\00\00\00\00\00\EC\04\00\00"  # noqa
# }
# {
# key(13) = "INFO/version\00"
# data(4) = "\04\00\00\00"
# }

import enum
import os

from base64 import b64decode, b64encode
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from middlewared.plugins.idmap_.idmap_constants import IDType
from middlewared.service_exception import MatchNotFound
from middlewared.utils import filter_list
from middlewared.utils.sid import db_id_to_rid
from middlewared.utils.tdb import (
    get_tdb_handle,
    TDBBatchAction,
    TDBBatchOperation,
    TDBDataType,
    TDBHandle,
    TDBOptions,
    TDBPathType,
)
from struct import pack, unpack
from time import time
from .constants import SMBPath

# Major and minor versions must be written to the passdb.tdb file
# Major version identifies version of struct samu.
MINOR_VERSION_KEY = 'INFO/minor_version'
MINOR_VERSION_VAL = b64encode(pack('<I', 0))
MAJOR_VERSION_KEY = 'INFO/version'
MAJOR_VERSION_VAL = b64encode(pack('<I', 4))

NTHASH_LEN = 16

# The following constants are taken from default values
# generated in samu_new() in source3/passdb/passdb.c
DEFAULT_HOURS_LEN = 21
PACKED_HOURS = pack(f'<{"B" * DEFAULT_HOURS_LEN}', *[0xff] * DEFAULT_HOURS_LEN)
UNKNOWN_6 = 0x000004ec  # unknown value in samba struct samu

USER_PREFIX = 'USER_'
RID_PREFIX = 'RID_'

PASSDB_TDB_OPTIONS = TDBOptions(TDBPathType.CUSTOM, TDBDataType.BYTES)
PASSDB_PATH = f'{SMBPath.PASSDB_DIR.path}/passdb.tdb'
PASSDB_TIME_T_MAX = 2085923199  # observed in recent samba versions. Should be output of get_time_t_max()


class PassdbMustReinit(Exception):
    def __init__(self, reason):
        self.errmsg = reason


class UserAccountControl(enum.IntFlag):
    """
    from librpc/idl/samr.idl and MS-SAMR 2.2.1.12

    account control (acct_ctrl / acct_flags) bits
    entries in enum are only ones that may possibly be relevant for local accounts
    We may expand as-needed to include more documented flags.
    """
    DISABLED = 0x00000001  # User account disabled
    NORMAL_ACCOUNT = 0x00000010  # Normal user account
    DONT_EXPIRE_PASSWORD = 0x00000200  # User password does not expire
    AUTO_LOCKED = 0x00000400  # Account auto locked
    PASSWORD_EXPIRED = 0x00020000  # Password expired


@dataclass(frozen=True)
class PDBTimes:
    logon: int
    logoff: int
    kickoff: int
    bad_password: int
    pass_last_set: int
    pass_can_change: int
    pass_must_change: int


@dataclass(frozen=True)
class PDBEntry:
    """
    Derived from SAMU_BUFFER_FORMAT_V3

    NOTE: buffer format v3 and v4 are identical
    These are extracted from on-disk passdb.tdb entry
    Some fields from the passdb are omitted because we will never allow
    changing values (for example unknown_6, lanman password)
    """
    username: str  # Unix username
    nt_username: str  # Windows username
    domain: str  # Windows domain name (netbios name of TrueNAS)
    full_name: str  # user's full name
    comment: str
    home_dir: str  # home directory
    dir_drive: str  # home directroy drive string
    logon_script: str
    profile_path: str
    user_rid: int
    group_rid: int  # Samba's pdbedit defaults to 513 (domain users)
    acct_desc: str  # User description string
    acct_ctrl: int
    nt_pw: str  # NT password hash
    logon_count: int
    bad_pw_count: int
    times: PDBTimes


def _add_version_info():
    """ add version info to new file """
    with get_tdb_handle(PASSDB_PATH, PASSDB_TDB_OPTIONS) as hdl:
        hdl.store(MINOR_VERSION_KEY, MINOR_VERSION_VAL)
        hdl.store(MAJOR_VERSION_KEY, MAJOR_VERSION_VAL)


def _unpack_samba_pascal_string(entry_bytes: bytes, raw: bool = False) -> tuple[str, bytes]:
    """
    samba pascal strings have length of string as uint precedening string data
    This method unpacks from entry_bytes and returns tuple of string value and
    remainaing bytes of data.
    """

    entry_len = unpack('<I', entry_bytes[0:4])[0]
    entry_bytes = entry_bytes[4:]
    if raw:
        entry = unpack(f'<{entry_len}s', entry_bytes[0: entry_len])[0]
    else:
        # the length encoded in pascal string includes null-termination
        # strip off extra NULL and decode prior to return
        entry = unpack(f'<{entry_len}s', entry_bytes[0: entry_len])[0][:-1].decode()

    return (entry, entry_bytes[entry_len:])


def _pack_samba_pascal_string(entry: str | bytes) -> bytes:
    """ pack given string / bytes into format expected in TDB file """
    if isinstance(entry, str):
        entry = entry.encode() + b'\x00'

    entry_len = pack('<I', len(entry))
    return entry_len + entry


def _unpack_pdb_bytes(entry_bytes: bytes) -> PDBEntry:
    """ This method unpacks a SAMU_BUFFER_FORMAT_V3 into PDBEntry object """
    # first seven entries are various timestamps encoded as signed 32 bit int
    times = PDBTimes(*unpack('<iiiiiii', entry_bytes[0:28]))
    entry_bytes = entry_bytes[28:]

    # next are a series of pascal strings
    username, entry_bytes = _unpack_samba_pascal_string(entry_bytes)
    domain, entry_bytes = _unpack_samba_pascal_string(entry_bytes)
    nt_username, entry_bytes = _unpack_samba_pascal_string(entry_bytes)
    full_name, entry_bytes = _unpack_samba_pascal_string(entry_bytes)
    homedir, entry_bytes = _unpack_samba_pascal_string(entry_bytes)
    dir_drive, entry_bytes = _unpack_samba_pascal_string(entry_bytes)
    logon_script, entry_bytes = _unpack_samba_pascal_string(entry_bytes)
    profile_path, entry_bytes = _unpack_samba_pascal_string(entry_bytes)
    acct_desc, entry_bytes = _unpack_samba_pascal_string(entry_bytes)
    workstations, entry_bytes = _unpack_samba_pascal_string(entry_bytes)
    comment, entry_bytes = _unpack_samba_pascal_string(entry_bytes)
    munged_dial, entry_bytes = _unpack_samba_pascal_string(entry_bytes)

    # next are rid values
    user_rid, group_rid = unpack('<II', entry_bytes[0:8])
    entry_bytes = entry_bytes[8:]

    lm_pw, entry_bytes = _unpack_samba_pascal_string(entry_bytes, True)
    nt_pw, entry_bytes = _unpack_samba_pascal_string(entry_bytes, True)
    nt_pw_history, entry_bytes = _unpack_samba_pascal_string(entry_bytes, True)

    acct_ctrl, logon_divs, hours_len = unpack('<iHi', entry_bytes[0:10])
    entry_bytes = entry_bytes[10:]

    hours, entry_bytes = _unpack_samba_pascal_string(entry_bytes, True)

    bad_pw_cnt, logon_cnt = unpack('<HH', entry_bytes[0:4])

    return PDBEntry(
        username=username,
        nt_username=nt_username,
        domain=domain,
        full_name=full_name,
        comment=comment,
        home_dir=homedir,
        dir_drive=dir_drive,
        logon_script=logon_script,
        profile_path=profile_path,
        acct_desc=acct_desc,
        acct_ctrl=acct_ctrl,
        nt_pw=nt_pw.hex().upper(),
        user_rid=user_rid,
        group_rid=group_rid,
        logon_count=logon_cnt,
        bad_pw_count=bad_pw_cnt,
        times=times
    )


def _pack_pdb_entry(entry: PDBEntry) -> bytes:
    """
    Pack information in PDBEntry into bytes for TDB insertion

    Some values are defaulted to empty strings because we do not
    provide a mechanism for setting / maintaining them from middleware
    or explicitly do not support the associated feature (such as lanman password)
    """
    data = pack(
        '<iiiiiii',
        entry.times.logon,
        entry.times.logoff,
        entry.times.kickoff,
        entry.times.bad_password,
        entry.times.pass_last_set,
        entry.times.pass_can_change,
        entry.times.pass_must_change,
    )

    data += _pack_samba_pascal_string(entry.username)
    data += _pack_samba_pascal_string(entry.domain)
    data += _pack_samba_pascal_string(entry.nt_username)
    data += _pack_samba_pascal_string(entry.full_name)
    data += _pack_samba_pascal_string(entry.home_dir)
    data += _pack_samba_pascal_string(entry.dir_drive)
    data += _pack_samba_pascal_string(entry.logon_script)
    data += _pack_samba_pascal_string(entry.profile_path)
    data += _pack_samba_pascal_string(entry.acct_desc)
    data += _pack_samba_pascal_string('')  # workstations
    data += _pack_samba_pascal_string(entry.comment)
    data += _pack_samba_pascal_string('')  # munged dial

    data += pack('<II', entry.user_rid, entry.group_rid)
    data += _pack_samba_pascal_string('')  # lanman password
    data += _pack_samba_pascal_string(bytes.fromhex(entry.nt_pw))
    data += _pack_samba_pascal_string('')  # NT password history
    data += pack('<IHi', entry.acct_ctrl, 168, DEFAULT_HOURS_LEN)
    data += _pack_samba_pascal_string(PACKED_HOURS)
    data += pack('<HHi', entry.bad_pw_count, entry.logon_count, UNKNOWN_6)

    return data


def _parse_passdb_entry(hdl: TDBHandle, tdb_key: str, tdb_val: str) -> PDBEntry:
    """
    Retrieve SAMU data based on passdb RID entry and parse bytes into a PDBEntry
    object.


    """
    key = f'{USER_PREFIX}{b64decode(tdb_val)[:-1].decode()}'
    try:
        if (pdb_bytes := hdl.get(f'{USER_PREFIX}{b64decode(tdb_val)[:-1].decode()}')) is None:
            # malformed passdb entry. Shouldn't happen we'll return None to force
            # rewrite
            raise PassdbMustReinit(f'{key}: passdb.tdb lacks expected key')
    except MatchNotFound:
        raise PassdbMustReinit(f'{key}: passdb.tdb lacks expected key') from None

    return _unpack_pdb_bytes(b64decode(pdb_bytes))


def passdb_entries(as_dict: bool = False) -> Iterable[PDBEntry, dict]:
    """ Iterate the passdb.tdb file

    Each SMB user contains two TDB entries. One that maps a RID value to the username
    and the other maps the username to a samu buffer. These are both written simultaneously
    under a transaction lock and so we should never be in a situation where they are
    inconsistent; however if we are unable to look up a USER entry based on the username
    in the RID entry, a PassdbMustReinit exception will be raised so that caller knows
    that the file should be rewritten.

    Params:
       as_dict - return as dictionary

    Returns:
       SMBGroupMap or SMBGroupMembership

    Raises:
       PassdbMustReinit - internal inconsistencies in passdb file
    """
    if not os.path.exists(PASSDB_PATH):
        _add_version_info()

    with get_tdb_handle(PASSDB_PATH, PASSDB_TDB_OPTIONS) as hdl:
        for entry in hdl.entries():
            if not entry['key'].startswith(RID_PREFIX):
                continue

            parsed = _parse_passdb_entry(hdl, entry['key'], entry['value'])
            yield asdict(parsed) if as_dict else parsed


def query_passdb_entries(filters: list, options: dict) -> list[dict]:
    """ Query passdb entries with default query-filters and query-options

    This provides a convenient query API for passdb entries. Wraps around
    passdb_entries() and same failure scenarios apply.

    Params:
        filters - standard query-filters
        options - standard query-options

    Returns:
        filterable returns with asdict() output of PDBEntry objects

    Raises:
       PassdbMustReinit - internal inconsistencies in passdb file
    """
    try:
        return filter_list(passdb_entries(as_dict=True), filters, options)
    except FileNotFoundError:
        return []


def insert_passdb_entries(entries: list[PDBEntry]) -> None:
    """ Insert multiple groupmap entries under a transaction lock

    Each PDBEntry requires two TDB insertions and so the entire list
    is submitted under a TDB transaction lock, which means that in case
    of failure changes are rolled back to the state prior to insertion.

    Entries that already exist will be overwritten.

    Params:
        entries - list of PDBEntry objects to be inserted

    Raises:
        TypeError - list item isn't PDBEntry object
        RuntimeError - TDB library error
    """

    if not os.path.exists(PASSDB_PATH):
        _add_version_info()

    batch_ops = []

    for entry in entries:
        if not isinstance(entry, PDBEntry):
            raise TypeError(f'{type(entry)}: not a PDBEntry')

        samu_data = _pack_pdb_entry(entry)
        batch_ops.extend([
            TDBBatchOperation(
                action=TDBBatchAction.SET,
                key=f'{USER_PREFIX}{entry.username.lower()}',
                value=b64encode(samu_data)
            ),
            TDBBatchOperation(
                action=TDBBatchAction.SET,
                key=f'{RID_PREFIX}{entry.user_rid:08x}',
                value=b64encode(entry.username.lower().encode() + b'\x00')
            )
        ])

    if len(batch_ops) == 0:
        # nothing to do, avoid taking lock
        return

    with get_tdb_handle(PASSDB_PATH, PASSDB_TDB_OPTIONS) as hdl:
        hdl.batch_op(batch_ops)


def delete_passdb_entry(username: str, rid: int) -> None:
    """ Delete a passdb entry under a transaction lock """
    if not os.path.exists(PASSDB_PATH):
        # passdb.tdb doesn't exist so nothing to do
        return

    with get_tdb_handle(PASSDB_PATH, PASSDB_TDB_OPTIONS) as hdl:
        # Do this under transaction lock to force atomicity of changes
        try:
            hdl.batch_op([
                TDBBatchOperation(
                    action=TDBBatchAction.DEL,
                    key=f'{USER_PREFIX}{username.lower()}'
                ),
                TDBBatchOperation(
                    action=TDBBatchAction.DEL,
                    key=f'{RID_PREFIX}{rid:08x}'
                )
            ])
        except RuntimeError:
            # entries do not exist
            pass


def update_passdb_entry(entry: PDBEntry) -> None:
    """ Update an existing passdb entry or insert a new one

    This method attempts to update an existing passdb entry with info in PDBEntry
    object. If any operations related to update fail then rollback to original
    status of TDB file is performed.

    If entry does not exist, then new one is inserted.

    Params:
        entry - PDBEntry object with samu data for user

    Raises:
        TypeError - not a PDBEntry
        RuntimeError - TDB library error
    """
    if not isinstance(entry, PDBEntry):
        raise TypeError(f'{type(entry)}: expected PDBEntry type.')

    if not os.path.exists(PASSDB_PATH):
        _add_version_info()

    with get_tdb_handle(PASSDB_PATH, PASSDB_TDB_OPTIONS) as hdl:
        batch_ops = []
        try:
            current_username = b64decode(hdl.get(f'{RID_PREFIX}{entry.user_rid:08x}'))[:-1].decode()
        except MatchNotFound:
            pass
        else:
            if current_username != entry.username:
                # name has changed. Make sure we clean up old entry under transaction
                # lock
                batch_ops.append(
                    TDBBatchOperation(
                        action=TDBBatchAction.DEL,
                        key=f'{USER_PREFIX}{current_username.lower()}'
                    ),
                )

        samu_data = _pack_pdb_entry(entry)
        batch_ops.extend([
            TDBBatchOperation(
                action=TDBBatchAction.SET,
                key=f'{USER_PREFIX}{entry.username.lower()}',
                value=b64encode(samu_data)
            ),
            TDBBatchOperation(
                action=TDBBatchAction.SET,
                key=f'{RID_PREFIX}{entry.user_rid:08x}',
                value=b64encode(entry.username.lower().encode() + b'\x00')
            )
        ])
        hdl.batch_op(batch_ops)


def user_entry_to_uac_flags(user_entry) -> UserAccountControl:
    """ helper function to convert user entry account flags to MS-SAMU User Account Control flags """
    flags_out = UserAccountControl.NORMAL_ACCOUNT

    if user_entry['locked']:
        flags_out |= UserAccountControl.AUTO_LOCKED

    if user_entry['password_disabled']:
        flags_out |= UserAccountControl.DISABLED

    return flags_out


def user_smbhash_to_nt_pw(username, smbhash) -> str:
    """ helper function to get the NT hash from `smbhash` data """
    if not smbhash:
        raise ValueError(f'{username}: no SMB hash available for user')

    if ':' in smbhash:
        # we may have a legacy entry in smbpasswd format
        smbhash = smbhash.split(':')[3]

    # Check that the SMB hash is actually a hex string of the required length
    if len(bytes.fromhex(smbhash)) != NTHASH_LEN:
        raise ValueError('smbhash has incorrect length')

    return smbhash


def user_entry_to_passdb_entry(
    netbiosname: str,
    user_entry: dict,
    existing_entry: dict = None,
) -> PDBEntry:
    """ Create an updated PDBEntry based on user-provided specifications

    This helper function creates a PDBEntry for later use in passdb insertion call. The
    intended use is for cases where struct SAMU encodes information that we may wish to
    preserve but are unable to due to not having corresponding fields in our middleware
    user entries.
    """
    if not user_entry['smb']:
        raise ValueError(f'{user_entry["username"]}: not an SMB user')

    if not user_entry['smbhash']:
        raise ValueError(f'{user_entry["username"]}: SMB hash not available')

    try:
        nt_pw = user_smbhash_to_nt_pw(user_entry['username'], user_entry['smbhash'])
    except Exception as exc:
        raise ValueError(
            f'{user_entry["username"]}: failed to parse SMB hash of {user_entry["smbhash"]}'
        ) from exc

    if user_entry['last_password_change']:
        if isinstance(user_entry['last_password_change'], int):
            pass_last_set = user_entry['last_password_change']
        else:
            pass_last_set = int(user_entry['last_password_change'].timestamp())
    else:
        pass_last_set = int(time())

    pdb_times = PDBTimes(
        logon=0,
        logoff=PASSDB_TIME_T_MAX,
        kickoff=PASSDB_TIME_T_MAX,
        bad_password=0,
        pass_last_set=pass_last_set,
        pass_can_change=0,
        pass_must_change=PASSDB_TIME_T_MAX
    )

    pdb_dict = {
        'username': user_entry['username'],
        'nt_username': '',
        'domain': netbiosname.upper(),
        'full_name': user_entry['full_name'],
        'comment': '',
        'home_dir': '',
        'dir_drive': '',
        'logon_script': '',
        'profile_path': '',
        'user_rid': db_id_to_rid(IDType.USER, user_entry['id']),
        'group_rid': 513,  # samba default -- domain users rid
        'acct_desc': '',
        'acct_ctrl': user_entry_to_uac_flags(user_entry),
        'nt_pw': nt_pw,
        'logon_count': 0,
        'bad_pw_count': 0,
        'times': pdb_times
    }

    if existing_entry:
        # preserve counters
        pdb_dict['logon_count'] = existing_entry['logon_count']
        pdb_dict['bad_pw_count'] = existing_entry['bad_pw_count']

    return PDBEntry(**pdb_dict)
