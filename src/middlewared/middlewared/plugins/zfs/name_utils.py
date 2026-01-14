import string

ALLOWED = string.ascii_letters + string.digits + u'-_.: '
MAXNAMELEN = 255


def is_valid_name_component(component: str) -> bool:
    for _char in component:
        if _char not in ALLOWED:
            return False
    return True


def is_valid_fs_name(name: str) -> bool:
    for i in name.split('/'):
        if not is_valid_name_component(i):
            return False
    return True


def is_valid_snap_name(name: str) -> bool:
    parts = name.split('@')
    return (
        len(parts) == 2
        and is_valid_fs_name(parts[0])
        and is_valid_name_component(parts[1])
    )


def is_valid_bmark_name(name: str) -> bool:
    parts = name.split('#')
    return (
        len(parts) == 2
        and is_valid_fs_name(parts[0])
        and is_valid_name_component(parts[1])
    )
