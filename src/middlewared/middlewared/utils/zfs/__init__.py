import os


def query_imported_fast_impl(name_filters: list[str] | None = None) -> dict[str, dict[str, str]]:
    # the equivalent of running `zpool list -H -o guid,name` from cli
    # name_filters will be a list of pool names
    out = dict()
    name_filters = name_filters or []
    with os.scandir('/proc/spl/kstat/zfs') as it:
        for entry in filter(lambda entry: not name_filters or entry.name in name_filters, it):
            if not entry.is_dir() or entry.name == '$import':
                continue

            guid = guid_fast_impl(entry.name)
            state = state_fast_impl(entry.name)
            out.update({guid: {'name': entry.name, 'state': state}})

    return out


def guid_fast_impl(pool: str) -> str:
    """
    Lockless read of zpool guid. Raises FileNotFoundError
    if pool not imported.
    """
    with open(f'/proc/spl/kstat/zfs/{pool}/guid') as f:
        return f.read().strip()


def state_fast_impl(pool: str) -> str:
    """
    Lockless read of zpool state. Raises FileNotFoundError
    if pool not imported.
    """
    with open(f'/proc/spl/kstat/zfs/{pool}/state') as f:
        return f.read().strip()
