import enum

from secrets import randbits
from middlewared.plugins.idmap_.idmap_constants import BASE_SYNTHETIC_DATASTORE_ID, IDType


DOM_SID_PREFIX = 'S-1-5-21-'
DOM_SID_SUBAUTHS = 3
MAX_VALUE_SUBAUTH = 2 ** 32
BASE_RID_USER = 20000
BASE_RID_GROUP = 200000


class DomainRid(enum.IntEnum):
    """ Defined in MS-DTYP Section 2.4.2.4
    This is subsest of well-known RID values defined in above document
    focused on ones that are of particular significance to permissions and
    SMB server behavior
    """
    ADMINISTRATOR = 500  # local administrator account
    GUEST = 501  # guest account
    ADMINS = 512  # domain admins account (local or joined)
    USERS = 513
    GUESTS = 514
    COMPUTERS = 515


class WellKnownSid(enum.Enum):
    """ Defined in MS-DTYP Section 2.4.2.4

    WARNING: entries may be added to the end of this enum, but the ordering of
    it must not change because it is used to determine GID assigned to the SID
    in samba's winbindd_idmap.tdb.  """
    NULL = 'S-1-0-0'
    WORLD = 'S-1-1-0'
    LOCAL = 'S-1-2-0'
    CONSOLE_LOGON = 'S-1-2-1'
    CREATOR_OWNER = 'S-1-3-0'
    CREATOR_GROUP = 'S-1-3-1'
    OWNER_RIGHTS = 'S-1-3-4'
    DIALUP = 'S-1-5-1'
    NETWORK = 'S-1-5-2'
    BATCH = 'S-1-5-3'
    INTERACTIVE = 'S-1-5-4'
    SERVICE = 'S-1-5-6'
    ANONYMOUS = 'S-1-5-7'
    AUTHENTICATED_USERS = 'S-1-5-11'
    TERMINAL_SERVER_USER = 'S-1-5-13'
    REMOTE_AUTHENTICATED_LOGON = 'S-1-5-14'
    SYSTEM = 'S-1-5-18'
    NT_AUTHORITY = 'S-1-5-19'
    NETWORK_SERVICE = 'S-1-5-20'
    BUILTIN_ADMINISTRATORS = 'S-1-5-32-544'
    BUILTIN_USERS = 'S-1-5-32-545'
    BUILTIN_GUESTS = 'S-1-5-32-546'

    @property
    def sid(self):
        return self.value

    @property
    def valid_for_mapping(self):
        """
        Put full mapping in the winbind_idmap.tdb file so that all TrueNAS servers are consistent.
        There is special behavior for builtins and so they are also excluded from this list because
        they are explicitly mapped in Samba's group_mapping.tdb file.
        """
        return self not in (
            WellKnownSid.NULL,
            WellKnownSid.BUILTIN_ADMINISTRATORS,
            WellKnownSid.BUILTIN_USERS,
            WellKnownSid.BUILTIN_GUESTS,
        )


VALID_API_SIDS = frozenset([
    WellKnownSid.WORLD.sid,
    WellKnownSid.OWNER_RIGHTS.sid,
    WellKnownSid.BUILTIN_ADMINISTRATORS.sid,
    WellKnownSid.BUILTIN_USERS.sid,
    WellKnownSid.BUILTIN_GUESTS.sid,
])


class lsa_sidtype(enum.IntEnum):
    """ librpc/idl/lsa.idl
    used for passdb and group mapping databases
    """
    USE_NONE = 0  # NOTUSED
    USER = 1  # user
    DOM_GRP = 2  # domain group
    DOMAIN = 3
    ALIAS = 4  # local group
    WKN_GRP = 5  # well-known group
    DELETED = 6  # deleted account
    INVALID = 7  # invalid account
    UNKNOWN = 8
    COMPUTER = 9
    LABEL = 10  # mandatory label


def random_sid() -> str:
    """ See MS-DTYP 2.4.2 SID """
    subauth_1 = randbits(32)
    subauth_2 = randbits(32)
    subauth_3 = randbits(32)

    return f'S-1-5-21-{subauth_1}-{subauth_2}-{subauth_3}'


def sid_is_valid(sid: str) -> bool:
    """
    This is validation function should be used with some caution
    as it only applies to SID values we reasonably expect to be used
    in SMB ACLs or for local user / group accounts
    """
    if not isinstance(sid, str):
        return False

    # Whitelist some well-known SIDs user may have
    if sid in VALID_API_SIDS:
        return True

    if not sid.startswith(DOM_SID_PREFIX):
        # not a domain sid
        return False

    subauths = sid[len(DOM_SID_PREFIX):].split('-')

    # SID may have a RID component appended
    if len(subauths) < DOM_SID_SUBAUTHS or len(subauths) > DOM_SID_SUBAUTHS + 1:
        return False

    for subauth in subauths:
        if not subauth.isdigit():
            return False

        subauth_val = int(subauth)
        if subauth_val < 1 or subauth_val > MAX_VALUE_SUBAUTH:
            return False

    return True


def get_domain_rid(sid: str) -> int:
    """ get rid component of the specified SID """
    if not sid_is_valid(sid):
        raise ValueError(f'{sid}: not a valid SID')

    if not sid.startswith(DOM_SID_PREFIX):
        raise ValueError(f'{sid}: not a domain SID')

    subauths = sid[len(DOM_SID_PREFIX):].split('-')
    if len(subauths) == DOM_SID_SUBAUTHS:
        raise ValueError(f'{sid}: does not contain a RID component')

    return int(subauths[-1])


def db_id_to_rid(id_type: IDType, db_id: int) -> int:
    """
    Simple algorithm to convert a datastore ID into RID value. Has been
    in use since TrueNAS 12. May not be changed because it will break
    SMB share ACLs
    """
    if not isinstance(db_id, int):
        raise ValueError(f'{db_id}: Not an int')

    if db_id >= BASE_SYNTHETIC_DATASTORE_ID:
        raise ValueError('Not valid for users and groups from directory services')

    match id_type:
        case IDType.USER:
            return db_id + BASE_RID_USER
        case IDType.GROUP:
            return db_id + BASE_RID_GROUP
        case _:
            raise ValueError(f'{id_type}: unknown ID type')
