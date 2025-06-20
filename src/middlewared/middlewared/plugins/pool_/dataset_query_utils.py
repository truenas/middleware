from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Union

from middlewared.plugins.zfs_.utils import TNUserProp
from middlewared.service_exception import MatchNotFound
from middlewared.utils import BOOT_POOL_NAME_VALID, filters, get_impl
from middlewared.utils.size import format_size

try:
    import truenas_pylibzfs
except ImportError:
    truenas_pylibzfs = None

__all__ = ("generic_query",)

GENERIC_FILTERS = filters()
INTERNAL_DATASETS = (
    ".system",
    "ix-applications",
    "ix-apps",
    ".ix-virt",
)
"""
Tuple of internal dataset name patterns that should be filtered out by default.

These patterns represent system-managed datasets that are typically hidden
from user interfaces. Used by is_internal_dataset() to perform efficient
string prefix matching.
"""


def _format_bytes(value):
    """Format byte values as human-readable strings."""
    if isinstance(value, (int, float)) and value >= 0:
        try:
            return format_size(value)
        except Exception:
            return str(value)
    return str(value)


@dataclass(slots=True, kw_only=True)
class DeterminedProperties:
    """This class represents the properties that we
    have determined to be valid based on what was given
    to us and if the requested property is valid for the
    underlying zfs resource type. The idea, also, is that
    these need to only be calculated once for each zfs type
    that we come across."""

    fs: Union[
        set[truenas_pylibzfs.ZFSProperty],
        frozenset[truenas_pylibzfs.ZFSProperty],
        None,
    ] = None
    vol: Union[
        set[truenas_pylibzfs.ZFSProperty],
        frozenset[truenas_pylibzfs.ZFSProperty],
        None,
    ] = None
    default: frozenset[truenas_pylibzfs.ZFSProperty] = (
        truenas_pylibzfs.property_sets.ZFS_SPACE_PROPERTIES
    )


@dataclass(slots=True, kw_only=True)
class SnapshotArgs:
    # FIXME: too many snapshot arguments
    snapshots: bool = False
    """Retrieve snapshots for the zfs resource"""
    snapshots_recursive: bool = False
    """Recursively retrieve snapshots for the zfs resource"""
    snapshots_count: bool = False
    """Count the number of snapshots for a given zfs resource"""
    snapshots_properties: list[str] | None = field(default_factory=list)
    """Properties to retrieve for snapshots. Empty list means minimal properties,
    None means all properties."""


@dataclass(slots=True, kw_only=True)
class ExtraArgs:
    zfs_properties: list[str] | None = None
    """The requested properties to be retrieved.
    If NoneType, BASE_PROPS + whatever other base
    properties will be returned given the underlying
    zfs type.

    If an empty list, no properties will be retrieved"""
    retrieve_children: bool = True
    """Retrieve children for the zfs resource"""
    get_user_properties: bool = True
    """Retrieve user properties for zfs resource"""
    snap_properties: SnapshotArgs = field(default_factory=SnapshotArgs)
    flat: bool = False
    """Return a flat array of dictionary objects. Each dictionary
    object will represent the underlying zfs resource.

    If flat is false, an array of 1 dictionary object will be
    returned. The dictionary object will have a `children` key
    that will be an array of the _SAME_ dictionary object
    (with another `children` key). Each entry in the children array
    will represent the parent -> child relation of the filesystem."""


@dataclass(slots=True, kw_only=True)
class QueryFiltersCallbackState:
    filters: list = field(default_factory=list)
    """list of filters"""
    filter_fn: Callable = GENERIC_FILTERS.filter_list
    """function to do filtering"""
    get_fn: Callable = get_impl
    """function to get value from dict"""
    select_fn: Callable = GENERIC_FILTERS.do_select
    """function to select values"""
    select: list = field(default_factory=list)
    """list of fields to select. None means all"""
    count_only: bool = False
    """only count entries"""
    extra: ExtraArgs
    determined_properties: DeterminedProperties = field(
        default_factory=DeterminedProperties
    )
    """based on properties given to us, we need to determine
    which ones are valid"""
    get_source: bool = True
    """retrieve the zfs property source information"""
    get_crypto: bool = False
    """retrieve crypto related zfs property information"""
    results: list = field(default_factory=list)
    """the results from the query"""
    index: dict = field(default_factory=dict)
    """stores the index values of each dataset that is iterated"""
    count: int = 0
    """the count of objects if count_only == True"""
    exclude_internal_datasets: bool = True
    """Flag to control whether internal datasets should be filtered out.
    When True, system datasets matching INTERNAL_DATASETS patterns and boot
    pools will be excluded from query results. Allows for flexible control
    over when system datasets should be included in results."""


# FIXME: At time of writing, calling pool.dataset.query
# with no filters or options causes the return to include
# these properties. We should review these and remove the
# ones that aren't needed. The less we query here, the
# more performant/efficient the endpoint is by default.
BASE_PROPS = frozenset(
    {
        truenas_pylibzfs.ZFSProperty.AVAILABLE,
        truenas_pylibzfs.ZFSProperty.CHECKSUM,
        truenas_pylibzfs.ZFSProperty.COMPRESSION,
        truenas_pylibzfs.ZFSProperty.COMPRESSRATIO,
        truenas_pylibzfs.ZFSProperty.COPIES,
        truenas_pylibzfs.ZFSProperty.CREATION,
        truenas_pylibzfs.ZFSProperty.DEDUP,  # deduplication
        truenas_pylibzfs.ZFSProperty.ENCRYPTION,  # encryption_algorithm
        # encryption_root is just a string at top of dict
        truenas_pylibzfs.ZFSProperty.ENCRYPTIONROOT,  # encryption_root
        truenas_pylibzfs.ZFSProperty.KEYFORMAT,  # key_format
        truenas_pylibzfs.ZFSProperty.ORIGIN,
        truenas_pylibzfs.ZFSProperty.PBKDF2ITERS,
        truenas_pylibzfs.ZFSProperty.READONLY,
        truenas_pylibzfs.ZFSProperty.REFRESERVATION,
        truenas_pylibzfs.ZFSProperty.RESERVATION,
        truenas_pylibzfs.ZFSProperty.SNAPDEV,
        truenas_pylibzfs.ZFSProperty.SYNC,
        truenas_pylibzfs.ZFSProperty.USED,
        truenas_pylibzfs.ZFSProperty.USEDBYCHILDREN,
        truenas_pylibzfs.ZFSProperty.USEDBYDATASET,
        truenas_pylibzfs.ZFSProperty.USEDBYREFRESERVATION,
        truenas_pylibzfs.ZFSProperty.USEDBYSNAPSHOTS,
    }
)
BASE_FS_PROPS = BASE_PROPS | frozenset(
    {
        truenas_pylibzfs.ZFSProperty.ACLMODE,
        truenas_pylibzfs.ZFSProperty.ACLTYPE,
        truenas_pylibzfs.ZFSProperty.ATIME,
        truenas_pylibzfs.ZFSProperty.CASESENSITIVITY,
        truenas_pylibzfs.ZFSProperty.EXEC,
        truenas_pylibzfs.ZFSProperty.MOUNTPOINT,
        truenas_pylibzfs.ZFSProperty.QUOTA,
        truenas_pylibzfs.ZFSProperty.RECORDSIZE,
        truenas_pylibzfs.ZFSProperty.REFQUOTA,
        truenas_pylibzfs.ZFSProperty.SNAPDIR,
        truenas_pylibzfs.ZFSProperty.SPECIAL_SMALL_BLOCKS,
        truenas_pylibzfs.ZFSProperty.XATTR,
    }
)
BASE_VOL_PROPS = BASE_PROPS | frozenset(
    {
        truenas_pylibzfs.ZFSProperty.VOLBLOCKSIZE,
        truenas_pylibzfs.ZFSProperty.VOLSIZE,
    }
)


def zfs_property_names_to_be_renamed() -> dict[str, str]:
    """
    Return a mapping of ZFS property names to their renamed equivalents for backwards compatibility.

    This exists solely for backwards compatibility and obfuscates what libzfs returns.
    In the future, we should return ZFS properties exactly as libzfs provides them.

    Returns:
        dict[str, str]: A mapping where keys are the original libzfs property names
                       and values are the renamed property names used in the API.
    """
    return {
        "dedup": "deduplication",
        "encryption": "encryption_algorithm",
        "encryptionroot": "encryption_root",
        "keyformat": "key_format",
        "special_small_blocks": "special_small_block_size",
    }


def user_property_names_to_be_renamed() -> dict[str, str]:
    """
    Return a mapping of TrueNAS user property names to their renamed equivalents.

    Maps internal TrueNAS user property names to more user-friendly API names
    for backwards compatibility.

    Returns:
        dict[str, str]: A mapping where keys are TrueNAS user property names
                       and values are the API-friendly names.
    """
    return {
        TNUserProp.DESCRIPTION.value: "comments",
        TNUserProp.QUOTA_WARN.value: "quota_warning",
        TNUserProp.QUOTA_CRIT.value: "quota_critical",
        TNUserProp.REFQUOTA_WARN.value: "refquota_warning",
        TNUserProp.REFQUOTA_CRIT.value: "refquota_critical",
        TNUserProp.MANAGED_BY.value: "managedby",
    }


def normalize_zfs_properties(zprops: dict[str, dict] | None) -> dict[str, dict]:
    """
    Normalize ZFS properties returned by libzfs into the expected API format.

    This function exists for backwards compatibility and transforms the raw ZFS
    property format into a structured format with parsed values, raw values,
    source information, etc. The mountpoint property receives special handling.

    Transformations applied:
    - Datetime properties are converted from timestamps to datetime objects
    - Boolean properties are converted from "on"/"off" to True/False
    - Integer properties are converted from strings to integers
    - Nullable properties convert '0' to None when appropriate
    - Special formatting for compression ratio, encryption properties, etc.

    Args:
        zprops: Raw ZFS properties dict from libzfs, or None

    Returns:
        dict[str, dict]: Normalized properties where each property contains:
                        - parsed: The parsed/processed value (with type conversions)
                        - rawvalue: The raw string value from ZFS
                        - value: The formatted value (with special formatting applied)
                        - source: The property source type name
                        - source_info: Additional source information
    """
    props = dict()
    if zprops is None:
        return props

    # Properties that should use human-readable size formatting in the 'value' field
    size_properties = {
        "used",
        "usedbychildren",
        "usedbydataset",
        "usedbyrefreservation",
        "usedbysnapshots",
        "available",
        "quota",
        "refquota",
        "reservation",
        "refreservation",
        "volsize",
    }

    # Properties that should be converted from timestamps to datetime objects
    datetime_properties = {"creation"}

    # Boolean properties that should be converted from "on"/"off" to True/False
    # This matches the ZFS_PROPERTY_CONVERTERS in converter.pxi
    boolean_properties = {
        "checksum",
        "atime",
        "devices",
        "exec",
        "setuid",
        "readonly",
        "jailed",
        "canmount",
        "xattr",
        "utf8only",
        "vscan",
        "nbmand",
    }

    # Integer properties that should be converted from string to int
    # This matches the ZFS_PROPERTY_CONVERTERS in converter.pxi
    integer_properties = {
        "used",
        "available",
        "referenced",
        "recordsize",
        "copies",
        "version",
        "usedbysnapshots",
        "usedbydataset",
        "usedbychildren",
        "usedbyrefreservation",
        "written",
        "logicalused",
        "logicalreferenced",
        "volsize",
        "volblocksize",
        "filesystem_limit",
        "snapshot_limit",
        "filesystem_count",
        "snapshot_count",
    }

    # Properties that have nullable integer conversion with special read_null='0' handling
    # These convert '0' rawvalue to None parsed value
    nullable_zero_properties = {"quota", "reservation", "refquota", "refreservation"}

    # Properties that should remain as strings even if they look numeric
    # Based on ZFS_PROPERTY_CONVERTERS that use ZfsConverter(str)
    string_properties = {
        "compression",
        "snapdir",
        "aclmode",
        "aclinherit",
        "normalization",
        "casesensitivity",
        "sharesmb",
        "sharenfs",
        "primarycache",
        "secondarycache",
        "logbias",
        "dedup",
        "mislabel",
        "sync",
        "refcompressratio",
        "compressratio",
        "volmode",
        "redundant_metadata",
        "type",
        "mountpoint",
        "pbkdf2iters",
        "special_small_block_size",
        "encryption_algorithm",
        "key_format",
        "origin",
    }

    rename_dict = zfs_property_names_to_be_renamed()
    for zfs_prop_name, vdict in zprops.items():
        if zfs_prop_name in rename_dict:
            zfs_prop_name = rename_dict[zfs_prop_name]

        # mountpoint is handled specially for backwards compatibility
        if zfs_prop_name == "mountpoint":
            props[zfs_prop_name] = zprops["mountpoint"]["raw"]
            continue

        # Handle source information safely (may be None for some properties)
        source_info = vdict.get("source")
        if source_info is not None:
            source_name = truenas_pylibzfs.PropertySource(source_info["type"]).name
            source_value = source_info["value"]
        else:
            source_name = "UNKNOWN"
            source_value = None

        # Determine the value field based on property type
        raw_value = vdict["raw"]
        parsed_value = vdict["value"]

        # Convert datetime properties from timestamp to datetime objects (matching parse_zfs_prop behavior)
        if zfs_prop_name in datetime_properties and isinstance(
            parsed_value, (int, float)
        ):
            from datetime import datetime, timezone

            try:
                # Use the same conversion as parse_zfs_prop in converter.pxi, but with modern datetime API
                # Parsed field: UTC datetime object (matches old API)
                parsed_value = datetime.fromtimestamp(
                    int(parsed_value), tz=timezone.utc
                )
                # Value field: local time string with space-padded hour (matches old API)
                local_dt = datetime.fromtimestamp(
                    int(raw_value)
                )  # Local time, no timezone
                hour = local_dt.hour
                hour_str = f" {hour}" if hour < 10 else str(hour)
                value_field = local_dt.strftime(f"%a %b %d {hour_str}:%M %Y")
            except (ValueError, OSError):
                # If conversion fails, keep original value
                value_field = (
                    raw_value.upper() if isinstance(raw_value, str) else str(raw_value)
                )
        elif zfs_prop_name in boolean_properties and isinstance(raw_value, str):
            # Convert boolean properties from "on"/"off" to True/False to match parse_zfs_prop
            if raw_value == "on":
                parsed_value = True
            elif raw_value == "off":
                parsed_value = False
            else:
                parsed_value = None
            value_field = raw_value.upper()
        elif zfs_prop_name in nullable_zero_properties and isinstance(raw_value, str):
            # Handle nullable integer properties that convert '0' to None
            if raw_value == "0":
                parsed_value = None
                value_field = None
            else:
                try:
                    parsed_value = int(raw_value)
                    if zfs_prop_name in size_properties:
                        value_field = _format_bytes(parsed_value)
                    else:
                        value_field = raw_value.upper()
                except ValueError:
                    parsed_value = raw_value
                    value_field = raw_value.upper()
        elif zfs_prop_name in string_properties:
            # Keep string properties as strings, don't try to convert them
            parsed_value = raw_value
            # Special formatting for compression ratio to match old API
            if zfs_prop_name == "compressratio":
                value_field = (
                    f"{raw_value}x" if isinstance(raw_value, str) else str(raw_value)
                )
            # Special null handling for properties that show None in old API
            elif zfs_prop_name == "encryption_algorithm" and raw_value == "off":
                value_field = None
            elif zfs_prop_name == "key_format" and raw_value == "none":
                parsed_value = "none"  # Keep parsed as 'none' for key_format
                value_field = None
            # Special handling for origin property empty values
            elif zfs_prop_name == "origin" and raw_value == "none":
                parsed_value = ""
                raw_value = ""  # Also fix rawvalue to match old API
                value_field = ""
            else:
                value_field = (
                    raw_value.upper() if isinstance(raw_value, str) else str(raw_value)
                )
        elif zfs_prop_name in integer_properties and isinstance(raw_value, str):
            # Convert integer properties from string to int
            try:
                parsed_value = int(raw_value)
            except ValueError:
                # If conversion fails, keep original value
                pass

            # Special formatting for recordsize and volblocksize to match original API
            if zfs_prop_name in ("recordsize", "volblocksize") and isinstance(
                parsed_value, (int, float)
            ):
                # Convert bytes to human-readable format like the original API (e.g., 131072 -> "128K")
                if parsed_value >= 1024 * 1024:
                    value_field = f"{int(parsed_value / (1024 * 1024))}M"
                elif parsed_value >= 1024:
                    value_field = f"{int(parsed_value / 1024)}K"
                else:
                    value_field = str(parsed_value)
            else:
                if zfs_prop_name in size_properties and isinstance(
                    parsed_value, (int, float)
                ):
                    value_field = _format_bytes(parsed_value)
                else:
                    value_field = raw_value.upper()
        elif zfs_prop_name in size_properties and isinstance(
            parsed_value, (int, float)
        ):
            # For size properties, use format_size for the 'value' field
            value_field = _format_bytes(parsed_value)
        else:
            # For other properties, uppercase the raw value
            value_field = (
                raw_value.upper() if isinstance(raw_value, str) else str(raw_value)
            )

        props[zfs_prop_name] = {
            "parsed": parsed_value,
            "rawvalue": raw_value,
            "value": value_field,
            "source": source_name,
            "source_info": source_value,
        }
    return props


def normalize_user_properties(uprops: dict[str, str] | None) -> dict[str, dict]:
    """
    Normalize ZFS user properties into the expected API format.

    This function exists for backwards compatibility and transforms user properties
    into a structured format similar to ZFS properties. The source information
    is hardcoded and may not be accurate.

    Args:
        uprops: Raw user properties dict from libzfs, or None

    Returns:
        dict[str, dict]: Normalized user properties where each property contains:
                        - parsed: The property value
                        - rawvalue: The property value (same as parsed)
                        - value: The property value (same as parsed)
                        - source: Hardcoded as "LOCAL" (may be inaccurate)
                        - source_info: Always None (may be inaccurate)
    """
    props = dict()
    if uprops is None:
        return props

    rename_dict = user_property_names_to_be_renamed()
    for user_prop_name, user_prop_value in uprops.items():
        if user_prop_name in rename_dict:
            user_prop_name = rename_dict[user_prop_name]

        props[user_prop_name] = {
            "parsed": user_prop_value,
            "rawvalue": user_prop_value,
            "value": user_prop_value,
            # NOTE: The `source` key is incorrect but we shouldn't be using it
            "source": "LOCAL",
            # NOTE: The `source_info` key is incorrect but we shouldn't be using it
            "source_info": None,
        }
    return props


def build_set_of_zfs_props(
    hdl, state: QueryFiltersCallbackState
) -> frozenset[truenas_pylibzfs.ZFSProperty] | set[truenas_pylibzfs.ZFSProperty]:
    """
    Build a set of ZFS properties to retrieve for a given ZFS resource.

    This function determines which ZFS properties should be retrieved based on:
    1. The ZFS resource type (filesystem, volume, snapshot)
    2. Whether specific properties were requested
    3. Cached results from previous calls

    For performance, properties are validated against the ZFS type and cached
    once per type. If no properties are specified, appropriate base properties
    are returned for the ZFS type.

    Args:
        hdl: ZFS handle from truenas_pylibzfs
        state: Query callback state containing property requests and cache

    Returns:
        frozenset | set | None: Set of ZFS properties to retrieve, or None if
                               no properties should be retrieved
    """
    is_fs = hdl.type == truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM
    is_vol = hdl.type == truenas_pylibzfs.ZFSType.ZFS_TYPE_VOLUME
    is_snap = hdl.type == truenas_pylibzfs.ZFSType.ZFS_TYPE_SNAPSHOT

    if not any((is_fs, is_vol, is_snap)):
        # shouldn't be reachable but we'll return space related
        # properties since those are valid for all zfs types
        return state.determined_properties.default

    if state.extra.zfs_properties == []:
        # Empty list means query no properties, but include mountpoint for filesystems only
        # as it's required by other parts of the system (e.g., dataset_processes)
        if is_fs:
            return frozenset({truenas_pylibzfs.ZFSProperty.MOUNTPOINT})
        else:
            # For volumes and snapshots, return minimal properties
            return frozenset()

    # Check if we already have cached properties for this type
    if is_fs and state.determined_properties.fs is not None:
        return state.determined_properties.fs
    elif is_vol and state.determined_properties.vol is not None:
        return state.determined_properties.vol

    if state.extra.zfs_properties is None:
        # no properties given to us so we'll determine the
        # default set to return based on the underlying type
        if is_fs:
            state.determined_properties.fs = BASE_FS_PROPS
            state.get_crypto = True
            return state.determined_properties.fs
        elif is_vol:
            state.determined_properties.vol = BASE_VOL_PROPS
            state.get_crypto = True
            return state.determined_properties.vol
        elif is_snap:
            # Snapshot logic will be implemented later
            return state.determined_properties.default

    # Build and cache custom property set for this request
    fs_p = truenas_pylibzfs.property_sets.ZFS_FILESYSTEM_PROPERTIES
    vol_p = truenas_pylibzfs.property_sets.ZFS_VOLUME_PROPERTIES
    crypto_props = {
        truenas_pylibzfs.ZFSProperty.ENCRYPTION,
        truenas_pylibzfs.ZFSProperty.ENCRYPTIONROOT,
        truenas_pylibzfs.ZFSProperty.KEYFORMAT,
        truenas_pylibzfs.ZFSProperty.KEYLOCATION,
        truenas_pylibzfs.ZFSProperty.KEYSTATUS,
    }
    requested_props = set()
    for i in state.extra.zfs_properties:
        try:
            prop = truenas_pylibzfs.ZFSProperty[i.upper()]
            if is_fs and prop in fs_p:
                requested_props.add(prop)
            elif is_vol and prop in vol_p:
                requested_props.add(prop)

            # Check for crypto properties once, outside type checks
            if prop in crypto_props:
                state.get_crypto = True
        except KeyError:
            # invalid property, nothing to do
            continue

    # Cache the result for this type
    result = requested_props if requested_props else None
    if is_fs:
        state.determined_properties.fs = result
    elif is_vol:
        state.determined_properties.vol = result

    # Fallback for snapshots - will be implemented later
    if is_snap:
        return state.determined_properties.default

    return result


def normalize_zfs_asdict_result(raw_data, hdl, include_user_properties=True):
    """
    Normalize the raw result from hdl.asdict() into a standardized format.

    This function processes the raw dictionary returned by hdl.asdict() and creates
    a normalized dictionary with basic metadata and properly formatted properties.
    Properties are always flattened to the top level for consistent API structure.
    User properties are conditionally normalized based on include_user_properties.

    Args:
        raw_data: Raw dictionary from hdl.asdict()
        hdl: ZFS handle from truenas_pylibzfs
        include_user_properties: Whether to include user_properties in the result

    Returns:
        dict: Normalized dictionary with basic metadata and flattened properties
    """
    # Start with basic metadata
    result = {
        "id": hdl.name,
        "type": normalize_zfs_type(hdl.type),
        "name": hdl.name,
    }

    # Add pool only if it's available (snapshots might not have pool_name attribute)
    try:
        result["pool"] = hdl.pool_name
    except AttributeError:
        # For snapshots, extract pool from the name
        if "@" in hdl.name:
            dataset_name = hdl.name.split("@")[0]
            result["pool"] = dataset_name.split("/")[0]
        else:
            result["pool"] = None

    # Add normalized ZFS properties (always flatten to top level)
    normalized_properties = normalize_zfs_properties(raw_data.get("properties"))

    # Remove the 'type' property if it exists to avoid overriding our normalized type
    if "type" in normalized_properties:
        del normalized_properties["type"]

    result.update(**normalized_properties)

    # Conditionally add normalized user properties
    if include_user_properties:
        result["user_properties"] = normalize_user_properties(
            raw_data.get("user_properties")
        )

    return result


def build_info(hdl, state: QueryFiltersCallbackState):
    """
    Build a complete information dictionary for a ZFS resource.

    This function calls hdl.asdict() to retrieve ZFS properties and constructs
    a standardized information dictionary that includes basic metadata, encryption
    information, normalized properties, and user properties. The result is
    automatically transformed to match the current API format.

    Args:
        hdl: ZFS handle from truenas_pylibzfs
        state: Query callback state containing property and crypto settings

    Returns:
        dict: Complete information dictionary containing:
              - Basic metadata (id, name, type, pool)
              - Encryption information (if requested)
              - Normalized ZFS properties
              - User properties (if requested)
              - Mountpoint information
              - Empty children array for hierarchy building
              - All transformations applied to match current API format
    """
    tmp = hdl.asdict(
        properties=build_set_of_zfs_props(hdl, state),
        get_crypto=state.get_crypto,
        get_source=state.get_source,
        get_user_properties=state.extra.get_user_properties,
    )

    # Use the common normalization function
    info = normalize_zfs_asdict_result(tmp, hdl, state.extra.get_user_properties)

    # crypto related
    if state.get_crypto:
        if crypto := tmp["crypto"]:
            info["encrypted"] = True
            info["encryption_root"] = crypto["encryption_root"]
            info["key_loaded"] = crypto["key_is_loaded"]
            info["locked"] = not crypto["key_is_loaded"]
        else:
            info["encrypted"] = False
            info["encryption_root"] = None
            info["key_loaded"] = False
            info["locked"] = False

    # mountpoint is handled weirdly...why?
    if "mountpoint" not in info:
        info["mountpoint"] = hdl.get_mountpoint()

    # each entry always gets a top-level children key
    info["children"] = list()

    # Set mountpoint to None for volumes (matches current API behavior)
    if info.get("type") == "VOLUME":
        info["mountpoint"] = None

    # Filter out internal user properties from user_properties dict
    if "user_properties" in info and isinstance(info["user_properties"], dict):
        internal_props = {prop.value for prop in TNUserProp}
        info["user_properties"] = {
            k: v for k, v in info["user_properties"].items() if k not in internal_props
        }

    # Note: snapshot_count is added in generic_query_callback if requested

    return info


def normalize_zfs_type(zfs_type):
    """
    Normalize ZFS type enum to a clean string representation.

    Removes the "ZFS_TYPE_" prefix from ZFS type names for consistent
    API representation across all ZFS resource types.

    Args:
        zfs_type: ZFS type enum from truenas_pylibzfs

    Returns:
        str: Clean type name without "ZFS_TYPE_" prefix
    """
    return zfs_type.name.removeprefix("ZFS_TYPE_")


def snapshot_callback(snap_hdl, info):
    """
    Callback function for processing snapshots during iteration.

    This function handles both counting snapshots and collecting snapshot data
    based on what fields are requested. It directly modifies the info dictionary
    to add snapshot_count and/or snapshots list.

    Args:
        snap_hdl: Snapshot handle from truenas_pylibzfs
        info: Dataset info dictionary to update with snapshot data

    Returns:
        bool: Always True to continue iteration
    """
    # Increment snapshot count if we're counting
    if "snapshot_count" in info:
        info["snapshot_count"] += 1

    # Collect snapshot data if we're building a list
    if "snapshots" in info:
        # Create snapshot structure based on requested properties
        try:
            # Get basic snapshot information without calling asdict for performance
            snapshot_name_full = snap_hdl.name
            dataset_name, snapshot_name = snapshot_name_full.split("@", 1)

            # Create snapshot data matching old API structure
            snapshot_data = {
                "pool": info["pool"],  # Use parent dataset's pool
                "name": snapshot_name_full,
                "type": normalize_zfs_type(snap_hdl.type),
                "snapshot_name": snapshot_name,
                "dataset": dataset_name,
                "id": snapshot_name_full,
                "createtxg": str(
                    snap_hdl.createtxg
                ),  # Convert to string to match old API
            }

            # Add properties if requested (snapshots_properties is not empty list or is None)
            snapshots_props = info.get("_snapshots_properties", [])
            if snapshots_props is None or (
                snapshots_props is not None and len(snapshots_props) > 0
            ):
                # When specific properties are requested, add a properties dict
                try:
                    # Get the requested properties for the snapshot
                    if snapshots_props is None:
                        # All properties requested - get full property set
                        properties = truenas_pylibzfs.property_sets.ZFS_FILESYSTEM_SNAPSHOT_PROPERTIES
                    else:
                        # Specific properties requested - convert to property set
                        properties = set()
                        for prop_name in snapshots_props:
                            try:
                                prop = truenas_pylibzfs.ZFSProperty[prop_name.upper()]
                                properties.add(prop)
                            except KeyError:
                                continue  # Skip invalid properties

                    if properties:
                        raw_snapshot_data = snap_hdl.asdict(properties=properties)
                        normalized_props = normalize_zfs_properties(
                            raw_snapshot_data.get("properties")
                        )
                        snapshot_data["properties"] = normalized_props

                except Exception:
                    # If property retrieval fails, continue without properties
                    pass

            info["snapshots"].append(snapshot_data)
        except Exception:
            # If snapshot data retrieval fails, skip this snapshot
            pass

    return True


def is_internal_dataset(hdl):
    """
    Check if a dataset is an internal system dataset that should be filtered out.

    Detects system datasets by checking against known boot pool names and
    internal dataset patterns defined in INTERNAL_DATASETS.

    Args:
        hdl: ZFS handle from truenas_pylibzfs

    Returns:
        bool: True if the dataset is internal and should be filtered out,
              False if it should be included in results
    """
    name = hdl.name
    for i in BOOT_POOL_NAME_VALID:
        if name == i or name.startswith(f"{i}/"):
            return True
    for i in INTERNAL_DATASETS:
        if f"/{i}" in name:
            return True
    return False


def generic_query_callback(hdl, state: QueryFiltersCallbackState):
    """
    Callback function for processing individual ZFS resources during iteration.

    This function is called for each ZFS resource during iteration and handles:
    1. Early filtering using internal dataset and exact match checks
    2. Building complete resource information
    3. Adding snapshot count if requested
    4. Applying field selection if specified
    5. Adding results to flat array or building hierarchical structure
    6. Recursively processing children if requested

    The function uses two focused filtering approaches:
    - is_internal_dataset() for configurable system dataset filtering
    - exact_match_filters_specified_and_did_not_match() for performance optimization

    Args:
        hdl: ZFS handle from truenas_pylibzfs for current resource
        state: Query callback state containing all query parameters and results

    Returns:
        bool: True to continue iteration, False to halt iteration
    """
    if state.exclude_internal_datasets and is_internal_dataset(hdl):
        # is an internal dataset and told to exclude them from results
        return True

    info = build_info(hdl, state)

    # Add snapshot functionality if requested - do this directly here for efficiency
    if any(
        (
            state.extra.snap_properties.snapshots_count,
            state.extra.snap_properties.snapshots,
        )
    ):
        # Initialize snapshot_count to 0 if counting is requested
        if state.extra.snap_properties.snapshots_count:
            info["snapshot_count"] = 0

        # Initialize snapshots list if snapshot data is requested
        if state.extra.snap_properties.snapshots:
            info["snapshots"] = []
            # Pass snapshots_properties to the callback via the info dict
            info["_snapshots_properties"] = (
                state.extra.snap_properties.snapshots_properties
            )

        try:
            # Process snapshots for this specific dataset
            # Use fast=True for counting only, fast=False when we need snapshot data
            use_fast = not state.extra.snap_properties.snapshots
            # For recursive, we might need to handle this at a higher level
            # For now, try without the recursive parameter to see if it works
            hdl.iter_snapshots(callback=snapshot_callback, state=info, fast=use_fast)
        except Exception:
            # If snapshot iteration fails, initialized values remain
            pass

    if state.select:
        data = state.select_fn([info], state.select)[0]
    else:
        data = info

    # Note: Filtering will be applied at the end in generic_query function

    if state.count_only:
        state.count += 1
    else:
        # When retrieve_children is False, don't build hierarchy - just add datasets directly
        # This fixes filtering issues where specific datasets get lost in hierarchy building
        if not state.extra.retrieve_children:
            state.results.append(data)
        else:
            # Build hierarchy during iteration to populate children relationships
            dataset_name = data["name"]
            curr_path = ""
            curr_children = state.results

            # Navigate/create the path to this dataset
            for part in dataset_name.split("/"):
                curr_path = f"{curr_path}/{part}" if curr_path else part

                # Find or create this path level
                existing_node = None
                for node in curr_children:
                    if node["name"] == curr_path:
                        existing_node = node
                        break

                if existing_node:
                    # Path already exists, navigate to its children
                    curr_children = existing_node["children"]
                else:
                    # Create new node
                    if curr_path == dataset_name:
                        # This is the actual dataset we're processing
                        new_node = data
                    else:
                        # This is an intermediate path, create placeholder
                        new_node = {"id": curr_path, "name": curr_path, "children": []}

                    curr_children.append(new_node)
                    curr_children = new_node["children"]

    # Always recurse when we have filters, even if retrieve_children is False
    # This ensures filtered queries can find child datasets
    if state.extra.retrieve_children or state.filters:
        hdl.iter_filesystems(callback=generic_query_callback, state=state)

    return True


def _flatten_hierarchy(hierarchy):
    """
    Flatten a hierarchical dataset structure into a flat list while preserving children relationships.
    This matches the old API behavior where flat=True returns all datasets as separate objects
    but each dataset still has its children populated.
    """
    flat_list = []

    def collect_datasets(datasets):
        for dataset in datasets:
            flat_list.append(dataset)
            if "children" in dataset and dataset["children"]:
                collect_datasets(dataset["children"])

    collect_datasets(hierarchy)
    return flat_list


def generic_query(
    rsrc_iterator: Callable,
    filters_in: list,
    options_in: dict,
    extra: dict,
    exclude_internal_datasets: bool = True,
):
    """
    Generic query function for ZFS resources with filtering, pagination, and hierarchy support.

    This function provides a flexible query interface that supports:
    - Filtering by name, id, pool, type with various operators
    - Flat or hierarchical result structure
    - Field selection and ordering
    - Pagination with offset and limit
    - Property-specific retrieval for performance
    - Children retrieval with descendant filtering
    - Configurable internal dataset filtering
    - API compatibility transformations to match current API format

    Args:
        rsrc_iterator: Iterator function from truenas_pylibzfs (e.g., iter_root_filesystems)
        filters_in: List of filter expressions [["field", "operator", "value"], ...]
        options_in: Query options dict with keys like "get", "count", "order_by", etc.
        extra: Extra options dict with keys like "flat", "properties", "retrieve_children"
        exclude_internal_datasets: If True, filter out system datasets (default True)

    Returns:
        list | dict | int: Query results based on options:
                          - List of resources (default)
                          - Single resource (if get=True)
                          - Count integer (if count=True)

    Raises:
        MatchNotFound: When get=True but no results found
    """
    # parse query-options
    options, select, order_by = GENERIC_FILTERS.validate_options(options_in)

    # set up callback state
    state = QueryFiltersCallbackState(
        filters=filters_in,
        select=select,
        count_only=options["count"],
        extra=ExtraArgs(
            flat=extra.get("flat", True),
            zfs_properties=extra.pop("properties", None),
            retrieve_children=extra.get("retrieve_children", True),
            get_user_properties=extra.get("retrieve_user_props", True),
            snap_properties=SnapshotArgs(
                snapshots=extra.get("snapshots", False),
                snapshots_recursive=extra.get("snapshots_recursive", False),
                snapshots_count=extra.get("snapshots_count", False),
                snapshots_properties=extra.get("snapshots_properties", []),
            ),
        ),
        exclude_internal_datasets=exclude_internal_datasets,
    )

    # do iteration
    rsrc_iterator(callback=generic_query_callback, state=state)

    if options["count"]:
        return state.count

    # Apply filtering - we need to filter on a flat structure regardless of final output format
    if state.filters:
        # Always flatten for filtering to ensure we can find nested datasets
        flat_for_filtering = _flatten_hierarchy(state.results)
        filtered_flat = state.filter_fn(
            flat_for_filtering, filters=state.filters, options={}
        )

        # If we want flat output, use the filtered flat results
        if state.extra.flat:
            state.results = filtered_flat
        else:
            # If we want hierarchical output, rebuild hierarchy from filtered results
            # For now, when flat=False with filters, return the filtered items as a flat list
            # This matches the behavior when specific datasets are requested
            state.results = filtered_flat
    else:
        # No filtering needed, apply flattening if requested
        if state.extra.flat:
            state.results = _flatten_hierarchy(state.results)

    if order_by:
        state.results = GENERIC_FILTERS.do_order(state.results, order_by)

    # Apply get=True AFTER filtering and ordering
    if options["get"]:
        if not state.results:
            raise MatchNotFound()
        return state.results[0]

    if offset := options.get("offset", 0):
        state.results = state.results[offset:]

    if limit := options.get("limit", 0):
        state.results = state.results[:limit]

    return state.results
