import typing

__all__ = ("get_zpool_properties_impl",)


def get_zpool_properties_impl(
    pool: typing.Any, properties: set | None = None
) -> typing.Any:
    """Return selected pool properties as a struct_zpool_property.

    Calls pool.get_properties() with a set of ZPOOLProperty enum values.

    Args:
        pool: An already-opened pylibzfs pool object.
        properties: Set of ZPOOLProperty enum values, or None for all.

    Returns:
        A struct_zpool_property whose attributes are struct_zpool_prop_type
        objects with .value, .raw, and .source fields.
    """
    if properties is not None:
        return pool.get_properties(properties=properties)
    # When None, fetch all known properties
    from truenas_pylibzfs import ZPOOLProperty

    return pool.get_properties(properties=set(ZPOOLProperty))
