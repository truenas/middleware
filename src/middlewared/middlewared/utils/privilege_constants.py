import enum

ALLOW_LIST_FULL_ADMIN = {'method': '*', 'resource': '*'}


class LocalBuiltinAdminGroups(enum.IntEnum):
    """Single point of reference for admin groups"""
    TRUENAS_WEBSHARE_ADMINISTRATORS = 445
    BUILTIN_ADMINISTRATORS = 544
    TRUENAS_READONLY_ADMINISTRATORS = 951
    TRUENAS_SHARING_ADMINISTRATORS = 952


class LocalBuiltinGroups(enum.IntEnum):
    """Single point of reference for non-admin groups"""
    FTP = 14
    BUILTIN_USERS = 545
    APPS = 568
