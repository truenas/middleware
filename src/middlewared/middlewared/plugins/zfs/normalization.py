from types import MappingProxyType
from typing import Any

from middlewared.plugins.zfs_.utils import TNUserProp

__all__ = ("normalize_asdict_result",)

USER_PROP_RENAME_DICT = MappingProxyType(
    {
        TNUserProp.DESCRIPTION.value: "comments",
        TNUserProp.QUOTA_WARN.value: "quota_warning",
        TNUserProp.QUOTA_CRIT.value: "quota_critical",
        TNUserProp.REFQUOTA_WARN.value: "refquota_warning",
        TNUserProp.REFQUOTA_CRIT.value: "refquota_critical",
        TNUserProp.MANAGED_BY.value: "managedby",
    }
)


def normalize_asdict_result(
    result: dict[str, Any], *, normalize_source: bool, get_crypto: bool = False
) -> dict[str, Any]:
    """
    Normalize ZFS resource dictionary result from truenas_pylibzfs asdict() method.

    This function transforms the raw ZFS resource dictionary returned by the
    truenas_pylibzfs library into a normalized format suitable for API responses.

    Transformations performed:
    1. Removes the 'type_enum' key (internal enum object)
    2. Replaces the 'crypto' key with a normalized encryption state when `get_crypto` is set, and removes it
       otherwise (crypto properties are included in properties if requested)
    3. Converts property source enum values to string names
    4. Renames known user properties according to USER_PROP_RENAME_DICT
    5. Preserves unknown user properties as-is
    6. Removes 'ZFS_TYPE_' prefix from the 'type' key

    Args:
        result (dict): Raw ZFS resource dictionary from truenas_pylibzfs asdict().
                      Expected to contain keys: name, type, properties, user_properties.
                      The properties dict contains property values with source information.
                      The user_properties dict contains custom ZFS user properties.
        normalize_source (bool): If True, will normalize the `source` key.
        get_crypto (bool): If True, will replace the `crypto` key with the normalized encryption state.

    Returns:
        dict: The same dictionary object modified in-place with normalized values.
              Property sources will be converted from enum objects to string names.
              Known user properties will be renamed according to mapping rules.

    Note:
        This function modifies the input dictionary in-place and returns the same
        object reference. Property source enum objects are converted to their
        string names (e.g., PropertySource.NONE becomes "NONE").

    Example:
        >>> raw_result = {
        ...     "type_enum": <ZFSType.ZFS_TYPE_FILESYSTEM>,
        ...     "name": "pool/dataset",
        ...     "type": "ZFS_TYPE_FILESYSTEM",
        ...     "crypto": None,
        ...     "properties": {
        ...         "used": {
        ...             "source": {"type": <PropertySource.NONE>, "value": None}
        ...         }
        ...     },
        ...     "user_properties": {
        ...         "org.freenas:description": "My dataset"
        ...     }
        ... }
        >>> normalized = normalize_asdict_result(raw_result)
        >>> normalized = {
        ...     "name": "pool/dataset",
        ...     "type": "FILESYSTEM",
        ...     "properties": {
        ...         "used": {
        ...             "source": {"type": "NONE", "value": None}
        ...         }
        ...     },
        ...     "user_properties": {
        ...         "comments": "My dataset"
        ...     }
        ... }
    """
    # remove the enum object
    result.pop("type_enum", None)

    if get_crypto:
        crypto = result.get("crypto")
        result["crypto"] = {
            "encrypted": crypto is not None,
            "encryption_root": crypto["encryption_root"] if crypto else None,
            "key_loaded": bool(crypto and crypto["key_is_loaded"]),
            "locked": bool(crypto and not crypto["key_is_loaded"]),
        }
    else:
        # remove crypto key. if someone has requested
        # propert(y/ies) and any of those are crypto
        # related, then the propert(y/ies) will be
        # be included automatically. No need to have
        # a top-level crypto key that is a sub-set of
        # the data that is already included
        result.pop("crypto", None)

    result["type"] = result["type"].removeprefix("ZFS_TYPE_")

    if normalize_source and result["properties"]:
        # update zfs properties
        for i in result["properties"].values():
            # looks like:
            # {'source': {'type': <PropertySource.NONE: 1>, 'value': None}}
            # converting it to:
            # {'source': {'type': 'NONE', 'value': None}}
            i["source"]["type"] = i["source"]["type"].name

    # update user properties
    if result["user_properties"]:
        final = dict()
        for k, v in result["user_properties"].items():
            if k in USER_PROP_RENAME_DICT:
                # looks like:
                # {'org.freenas:refquota_critical': '95'}
                # converting it to:
                # {'refquota_critical': '95'}
                final[USER_PROP_RENAME_DICT[k]] = v
            else:
                # leave it as-is
                final[k] = v
        result["user_properties"] = final
    return result
