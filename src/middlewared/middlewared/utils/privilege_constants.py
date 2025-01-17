import enum

ALLOW_LIST_FULL_ADMIN = {'method': '*', 'resource': '*'}


class LocalAdminGroups(enum.IntEnum):
    BUILTIN_ADMINISTRATORS = 544
