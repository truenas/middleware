import enum
import wbclient

TRUENAS_IDMAP_MAX = 2147000000
TRUENAS_IDMAP_DEFAULT_LOW = 90000001
SID_LOCAL_USER_PREFIX = "S-1-22-1-"
SID_LOCAL_GROUP_PREFIX = "S-1-22-2-"
SID_BUILTIN_PREFIX = "S-1-5-32-"
MAX_REQUEST_LENGTH = 100


class IDType(enum.IntEnum):
    """
    SSSD and libwbclient use identical values for id types
    """
    USER = wbclient.ID_TYPE_UID
    GROUP = wbclient.ID_TYPE_GID
    BOTH = wbclient.ID_TYPE_BOTH

    def wbc_str(self):
        # py-libwbclient uses string repesentation of id type
        if self == IDType.USER:
            val = "UID"
        elif self == IDType.GROUP:
            val = "GID"
        else:
            val = "BOTH"

        return val
