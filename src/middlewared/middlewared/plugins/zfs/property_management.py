from dataclasses import dataclass
from typing import TypeAlias

from truenas_pylibzfs import property_sets, ZFSProperty, ZFSType

__all__ = ("build_set_of_zfs_props", "build_set_of_zfs_snapshot_props", "DeterminedProperties")


ZFSPropSetType: TypeAlias = frozenset["ZFSProperty"]
ZFSResourceType: TypeAlias = "ZFSType"


@dataclass(slots=True, frozen=True, kw_only=True)
class ZFSPropertyTemplates:
    default: ZFSPropSetType | None = None
    """The default set of zfs properties to be retrieved if \
    none are provided."""
    fs: ZFSPropSetType | None = None
    """All available set of zfs properties for filesystems."""
    fs_ro: ZFSPropSetType | None = None
    """All available set of readonly zfs properties for filesystems."""
    vol: ZFSPropSetType | None = None
    """All available set of zfs properties for volumes."""
    vol_ro: ZFSPropSetType | None = None
    """All available set of readonly zfs properties for volumes."""
    crypto: ZFSPropSetType | None = None
    """All available zfs encryption related properties."""

    @classmethod
    def generate(cls):
        """Generate ZFS property templates from available property sets.

        Returns:
            ZFSPropertyTemplates: A new instance with property sets populated
                from truenas_pylibzfs if available, otherwise empty templates.
        """
        if property_sets is not None:
            return cls(
                default=property_sets.ZFS_SPACE_PROPERTIES,
                fs=property_sets.ZFS_FILESYSTEM_PROPERTIES,
                fs_ro=property_sets.ZFS_FILESYSTEM_READONLY_PROPERTIES,
                vol=property_sets.ZFS_VOLUME_PROPERTIES,
                vol_ro=property_sets.ZFS_VOLUME_READONLY_PROPERTIES,
                crypto=frozenset(
                    (
                        ZFSProperty.ENCRYPTION,
                        ZFSProperty.ENCRYPTIONROOT,
                        ZFSProperty.KEYFORMAT,
                        ZFSProperty.KEYLOCATION,
                        ZFSProperty.KEYSTATUS,
                    )
                ),
            )
        return cls()


PROPERTY_TEMPLATES = ZFSPropertyTemplates.generate()


@dataclass(slots=True, kw_only=True)
class DeterminedProperties:
    """This class represents the properties that we
    have determined to be valid based on what was given
    to us and if the requested property is valid for the
    underlying zfs resource type. The idea, also, is that
    these need to only be calculated once for each zfs type
    that we come across."""

    fs: ZFSPropSetType | None = None
    vol: ZFSPropSetType | None = None
    fs_snap: ZFSPropSetType | None = None
    vol_snap: ZFSPropSetType | None = None
    default: ZFSPropSetType | None = None


def __build_cache(
    hdl_type: ZFSResourceType, req_props: list[str], det_props: DeterminedProperties
) -> frozenset["ZFSProperty"]:
    """Build and cache a set of valid ZFS properties for a specific resource type.

    Args:
        hdl_type: The ZFS resource type (filesystem, or volume)
        req_props: List of requested property names as strings
        det_props: DeterminedProperties instance to cache results in

    Returns:
        frozenset[ZFSProperty]: Set of valid ZFS properties for the type.
            Returns empty frozenset if no valid properties found.
    """
    requested_props = set()
    is_fs = hdl_type == ZFSType.ZFS_TYPE_FILESYSTEM
    is_vol = hdl_type == ZFSType.ZFS_TYPE_VOLUME
    for i in req_props:
        try:
            prop = ZFSProperty[i.upper()]
        except KeyError:
            # invalid property, nothing to do
            continue

        if is_fs and prop in property_sets.ZFS_FILESYSTEM_PROPERTIES:
            requested_props.add(prop)
        elif is_vol and prop in property_sets.ZFS_VOLUME_PROPERTIES:
            requested_props.add(prop)

        if prop in PROPERTY_TEMPLATES.crypto:
            # if any property requested is a crypto property,
            # we're going to include the other crypto related
            # properties for the convenience of the api user
            requested_props |= PROPERTY_TEMPLATES.crypto

    # Cache the result for this type
    requested_props = requested_props or set()
    if hdl_type == ZFSType.ZFS_TYPE_FILESYSTEM:
        det_props.fs = requested_props
    elif hdl_type == ZFSType.ZFS_TYPE_VOLUME:
        det_props.vol = requested_props

    return frozenset(requested_props)


def build_set_of_zfs_props(
    hdl_type: ZFSResourceType,
    det_props: DeterminedProperties,
    req_props: list[str] | None,
) -> frozenset["ZFSProperty"] | None:
    """Build a set of ZFS properties to retrieve for a given ZFS resource.

    This function determines which ZFS properties should be retrieved based on
    the resource type and requested properties. It uses caching to avoid
    recomputing property sets for the same resource types.

    Args:
        hdl_type: The ZFS resource type (filesystem, volume, or snapshot)
        det_props: DeterminedProperties instance used for caching results
        req_props: List of requested property names as strings, or None
            for no properties. An empty list (default) requests space
            related properties.

    Returns:
        frozenset[ZFSProperty] | None: Set of valid ZFS properties to retrieve,
            default properties if req_props is None, or None if no properties
            should be retrieved (empty req_props list or unsupported type).
    """
    if req_props is None:
        # If the req_props (requested properties) is None, then
        # the user explicitly requested no zfs properties be retrieved
        return None
    elif req_props == [] or hdl_type not in (
        ZFSType.ZFS_TYPE_FILESYSTEM,
        ZFSType.ZFS_TYPE_VOLUME,
    ):
        # No properties were requested, or unsupported resource type
        return PROPERTY_TEMPLATES.default

    # Check if we already have cached properties for this type
    if hdl_type == ZFSType.ZFS_TYPE_FILESYSTEM and det_props.fs is not None:
        return det_props.fs
    elif hdl_type == ZFSType.ZFS_TYPE_VOLUME and det_props.vol is not None:
        return det_props.vol

    # Now cache and return the zfs properties for this type
    return __build_cache(hdl_type, req_props, det_props)


def __build_snapshot_cache(
    parent_type: ZFSResourceType, req_props: list[str], det_props: DeterminedProperties
) -> frozenset["ZFSProperty"]:
    """Build and cache a set of valid ZFS properties for snapshot of a specific parent type.

    Args:
        parent_type: The parent ZFS resource type (filesystem or volume)
        req_props: List of requested property names as strings
        det_props: DeterminedProperties instance to cache results in

    Returns:
        frozenset[ZFSProperty]: Set of valid ZFS snapshot properties for the parent type.
    """
    is_fs = parent_type == ZFSType.ZFS_TYPE_FILESYSTEM
    is_vol = parent_type == ZFSType.ZFS_TYPE_VOLUME

    # Get the valid snapshot properties for this parent type
    if is_fs:
        valid_props = property_sets.ZFS_FILESYSTEM_SNAPSHOT_PROPERTIES
    else:
        valid_props = property_sets.ZFS_VOLUME_SNAPSHOT_PROPERTIES

    requested_props = set()
    for i in req_props:
        try:
            prop = ZFSProperty[i.upper()]
        except KeyError:
            continue

        if prop in valid_props:
            requested_props.add(prop)

    # Cache the result for this parent type
    requested_props = frozenset(requested_props) if requested_props else frozenset()
    if is_fs:
        det_props.fs_snap = requested_props
    elif is_vol:
        det_props.vol_snap = requested_props

    return requested_props


def build_set_of_zfs_snapshot_props(
    parent_type: ZFSResourceType,
    det_props: DeterminedProperties,
    req_props: list[str] | None,
) -> frozenset["ZFSProperty"] | None:
    """Build a set of ZFS properties to retrieve for a snapshot.

    Unlike datasets, snapshots have NO default properties. Callers must
    explicitly request what they need. This is a hot code path optimization.

    Args:
        parent_type: The parent ZFS resource type (filesystem or volume)
        det_props: DeterminedProperties instance used for caching results
        req_props: List of requested property names as strings. None or
            empty list means no properties will be retrieved.

    Returns:
        frozenset[ZFSProperty] | None: Set of valid ZFS snapshot properties,
            or None if no properties should be retrieved.
    """
    # None or empty list = no properties (caller must be explicit)
    if not req_props:
        return None

    is_fs = parent_type == ZFSType.ZFS_TYPE_FILESYSTEM
    is_vol = parent_type == ZFSType.ZFS_TYPE_VOLUME

    # Check if we already have cached properties for this parent type
    if is_fs and det_props.fs_snap is not None:
        return det_props.fs_snap
    elif is_vol and det_props.vol_snap is not None:
        return det_props.vol_snap

    return __build_snapshot_cache(parent_type, req_props, det_props)
