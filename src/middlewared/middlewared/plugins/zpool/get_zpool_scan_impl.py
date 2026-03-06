import typing

__all__ = ("get_zpool_scan_impl",)


def get_zpool_scan_impl(pool: typing.Any) -> typing.Any | None:
    """Return scrub/scan information for a pool.

    Calls pool.scrub_info() which returns a struct_zpool_scrub.
    Returns None if no scan has ever run (state is NONE).

    Args:
        pool: An already-opened pylibzfs pool object.

    Returns:
        A struct_zpool_scrub, or None if no scan has run.
    """
    scrub = pool.scrub_info()
    if scrub is None or scrub.state.name == "NONE":
        # scrub_info() returns None when the pool
        # has never had a scan initiated
        return None
    return scrub
