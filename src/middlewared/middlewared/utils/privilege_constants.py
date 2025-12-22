import enum

ALLOW_LIST_FULL_ADMIN = {'method': '*', 'resource': '*'}


class LocalAdminGroups(enum.IntEnum):
    """Single point of reference for special groups"""
    FTP = 14
    TRUENAS_WEBSHARE_ADMINISTRATORS = 445
    BUILTIN_ADMINISTRATORS = 544
    BUILTIN_USERS = 545
    APPS = 568
    TRUENAS_READONLY_ADMINISTRATORS = 951
    TRUENAS_SHARING_ADMINISTRATORS = 952
