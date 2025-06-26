# Utilities that wrap around samba's group_mapping.tdb file
#
# test coverage provided by src/middlewared/middlewared/pytest/unit/utils/test_groupmap.py
# sample tdb contents (via tdbdump)
#
# {
# key(23) = "UNIXGROUP/S-1-5-32-546\00"
# data(16) = "\83J]\05\04\00\00\00Guests\00\00"
# }
# {
# key(58) = "UNIXGROUP/S-1-5-21-1137207236-3870220311-645177593-200042\00"
# data(40) = "\B8\03\00\00\04\00\00\00truenas_sharing_administrators\00\00"
# }
# {
# key(55) = "UNIXGROUP/S-1-5-21-1137207236-3870220311-645177593-512\00"
# data(32) = " \02\00\00\04\00\00\00builtin_administrators\00\00"
# }
# {
# key(58) = "UNIXGROUP/S-1-5-21-1137207236-3870220311-645177593-200090\00"
# data(23) = "!\02\00\00\04\00\00\00builtin_users\00\00"
# }
# {
# key(55) = "UNIXGROUP/S-1-5-21-1137207236-3870220311-645177593-514\00"
# data(24) = "\22\02\00\00\04\00\00\00builtin_guests\00\00"
# }
# {
# key(58) = "UNIXGROUP/S-1-5-21-1137207236-3870220311-645177593-200041\00"
# data(41) = "\B7\03\00\00\04\00\00\00truenas_readonly_administrators\00\00"
# }
# {
# key(54) = "MEMBEROF/S-1-5-21-1137207236-3870220311-645177593-512\00"
# data(13) = "S-1-5-32-544\00"
# }
# {
# key(23) = "UNIXGROUP/S-1-5-32-544\00"
# data(24) = "\81J]\05\04\00\00\00Administrators\00\00"
# }
# {
# key(57) = "MEMBEROF/S-1-5-21-1137207236-3870220311-645177593-200090\00"
# data(13) = "S-1-5-32-545\00"
# }
# {
# key(54) = "MEMBEROF/S-1-5-21-1137207236-3870220311-645177593-514\00"
# data(13) = "S-1-5-32-546\00"
# }
# {
# key(23) = "UNIXGROUP/S-1-5-32-545\00"
# data(15) = "\82J]\05\04\00\00\00Users\00\00"
# }

import enum

from base64 import b64decode, b64encode
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from socket import htonl, ntohl
from middlewared.plugins.system_dataset.utils import SYSDATASET_PATH
from middlewared.utils import filter_list
from middlewared.utils.sid import (
    lsa_sidtype
)
from middlewared.utils.tdb import (
    get_tdb_handle,
    TDBBatchAction,
    TDBBatchOperation,
    TDBDataType,
    TDBOptions,
    TDBPathType,
)

UNIX_GROUP_KEY_PREFIX = 'UNIXGROUP/'
MEMBEROF_PREFIX = 'MEMBEROF/'

GROUP_MAPPING_TDB_OPTIONS = TDBOptions(TDBPathType.CUSTOM, TDBDataType.BYTES)


class GroupmapEntryType(enum.Enum):
    GROUP_MAPPING = enum.auto()  # conventional group mapping entry
    MEMBERSHIP = enum.auto()  # foreign alias member


class GroupmapFile(enum.Enum):
    DEFAULT = f'{SYSDATASET_PATH}/samba4/group_mapping.tdb'
    REJECT = f'{SYSDATASET_PATH}/samba4/group_mapping_rejects.tdb'


@dataclass(frozen=True)
class SMBGroupMap:
    sid: str
    gid: int
    sid_type: lsa_sidtype
    name: str
    comment: str


@dataclass(frozen=True)
class SMBGroupMembership:
    sid: str
    groups: tuple[str]


def _parse_unixgroup(tdb_key: str, tdb_val: str) -> SMBGroupMap:
    """
    parsing function to convert TDB key/value pair into SMBGroupMap

    Sample TDB key:
    "UNIXGROUP/S-1-5-21-1137207236-3870220311-645177593-200042\00"

    Sample TDB value:
    "\\B8\03\00\00\04\00\00\00truenas_sharing_administrators\00\00"

    first four bytes are gid, second four are sid type,
    remainder are two null-terminated strings.

    Returns a SMBGroupMap object in which `sid` attribute is populated with
    value from key and remaining attributes are populated from
    the TDB value.
    """
    sid = tdb_key[len(UNIX_GROUP_KEY_PREFIX):]
    data = b64decode(tdb_val)

    # unix groups are written into tdb file via tdb_pack
    gid = htonl(int.from_bytes(data[0:4]))
    sid_type = lsa_sidtype(htonl(int.from_bytes(data[4:8])))

    # remaining bytes are two null-terminated strings
    bname, bcomment = data[8:-1].split(b'\x00')
    return SMBGroupMap(sid, gid, sid_type, bname.decode(), bcomment.decode())


def _parse_memberof(tdb_key: str, tdb_val: str) -> SMBGroupMembership:
    """
    parsing function to convert TDB key/value pair into SMBGroupMembership

    Sample TDB key:
    "MEMBEROF/S-1-5-21-1137207236-3870220311-645177593-512\00"

    Sample TDB value:
    "S-1-5-32-544 S-1-5-32-545\00"

    TDB value is space-delimited list of alias SIDS of which the SID
    specified in the TDB key is a member of.

    Returns SMBGroupMembership object in which the `sid` attribute is set
    based on the TDB key and the `groups` attribute is a tuple of the sids
    specified in TDB value (groups of which _this_ sid is a member of).
    """
    sid = tdb_key[len(MEMBEROF_PREFIX):]
    data = b64decode(tdb_val)

    groups = tuple(data[:-1].decode().split())
    return SMBGroupMembership(sid, groups)


def _groupmap_to_tdb_key_val(group_map: SMBGroupMap) -> tuple[str, str]:
    """ convert a SMBGroupMap object to TDB key-value pair for insertion into TDB file """
    tdb_key = f'{UNIX_GROUP_KEY_PREFIX}{group_map.sid}'
    gid = ntohl(group_map.gid).to_bytes(4)
    sid_type = ntohl(group_map.sid_type).to_bytes(4)
    name = group_map.name.encode()
    comment = group_map.comment.encode()

    data = gid + sid_type + name + b'\x00' + comment + b'\x00'
    return (tdb_key, b64encode(data))


def _groupmem_to_tdb_key_val(group_mem: SMBGroupMembership) -> tuple[str, str]:
    """ convert a SMBGroupMembership object to TDB key-value pair for insertion into TDB file """
    tdb_key = f'{MEMBEROF_PREFIX}{group_mem.sid}'
    data = ' '.join(set(group_mem.groups)).encode() + b'\x00'
    return (tdb_key, b64encode(data))


def groupmap_entries(
    groupmap_file: GroupmapFile,
    as_dict: bool = False
) -> Iterable[SMBGroupMap, SMBGroupMembership, dict]:
    """ iterate the specified group_mapping.tdb file

    Params:
       as_dict - return as dictionary

    Returns:
       SMBGroupMap or SMBGroupMembership

    Raises:
       RuntimeError
       FileNotFoundError
    """
    if not isinstance(groupmap_file, GroupmapFile):
        raise TypeError(f'{type(groupmap_file)}: expected GroupmapFile type.')

    with get_tdb_handle(groupmap_file.value, GROUP_MAPPING_TDB_OPTIONS) as hdl:
        for entry in hdl.entries():
            if entry['key'].startswith(UNIX_GROUP_KEY_PREFIX):
                parser_fn = _parse_unixgroup
                entry_type = GroupmapEntryType.GROUP_MAPPING.name
            elif entry['key'].startswith(MEMBEROF_PREFIX):
                parser_fn = _parse_memberof
                entry_type = GroupmapEntryType.MEMBERSHIP.name
            else:
                continue

            if as_dict:
                yield {'entry_type': entry_type} | asdict(parser_fn(entry['key'], entry['value']))
            else:
                yield parser_fn(entry['key'], entry['value'])


def query_groupmap_entries(groupmap_file: GroupmapFile, filters: list, options: dict) -> list[dict]:
    try:
        return filter_list(groupmap_entries(groupmap_file, as_dict=True), filters, options)
    except FileNotFoundError:
        return []


def insert_groupmap_entries(
    groupmap_file: GroupmapFile,
    entries: list[SMBGroupMap | SMBGroupMembership]
) -> None:
    """ Insert multiple groupmap entries under a transaction lock """

    batch_ops = []

    for entry in entries:
        if isinstance(entry, SMBGroupMap):
            tdb_key, tdb_val = _groupmap_to_tdb_key_val(entry)
        elif isinstance(entry, SMBGroupMembership):
            tdb_key, tdb_val = _groupmem_to_tdb_key_val(entry)
        else:
            raise TypeError(f'{type(entry)}: unexpected group_mapping.tdb entry type')

        batch_ops.append(TDBBatchOperation(action=TDBBatchAction.SET, key=tdb_key, value=tdb_val))

    if len(batch_ops) == 0:
        # nothing to do, avoid taking lock
        return

    with get_tdb_handle(groupmap_file.value, GROUP_MAPPING_TDB_OPTIONS) as hdl:
        hdl.batch_op(batch_ops)


def delete_groupmap_entry(
    groupmap_file: GroupmapFile,
    entry_type: GroupmapEntryType,
    entry_sid: str
):
    if not isinstance(groupmap_file, GroupmapFile):
        raise TypeError(f'{type(groupmap_file)}: expected GroupmapFile type.')

    if not isinstance(entry_type, GroupmapEntryType):
        raise TypeError(f'{type(entry_type)}: expected GroumapEntryType.')

    match entry_type:
        case GroupmapEntryType.GROUP_MAPPING:
            tdb_key = f'{UNIX_GROUP_KEY_PREFIX}{entry_sid}'
        case GroupmapEntryType.MEMBERSHIP:
            tdb_key = f'{MEMBEROF_PREFIX}{entry_sid}'
        case _:
            raise TypeError(f'{entry_type}: unexpected GroumapEntryType.')

    with get_tdb_handle(groupmap_file.value, GROUP_MAPPING_TDB_OPTIONS) as hdl:
        hdl.delete(tdb_key)


def list_foreign_group_memberships(
    groupmap_file: GroupmapFile,
    alias_sid: str
) -> list[str]:
    """
    This performs equivalent of `net groupmap listsmem <sid>`. TDB entries associate
    a SID with a list of groups of which it is a member. This function does the reverse
    lookup by finding which groups are members of a given SID, and returns a list of
    SIDs.
    """
    if not isinstance(groupmap_file, GroupmapFile):
        raise TypeError(f'{type(groupmap_file)}: expected GroupmapFile type.')

    return [
        entry['sid'] for entry in query_groupmap_entries(groupmap_file, [
            ['entry_type', '=', GroupmapEntryType.MEMBERSHIP.name],
            ['groups', 'rin', alias_sid]
        ], {})
    ]
