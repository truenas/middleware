import pathlib

try:
    import truenas_pylibzfs
except ImportError:
    truenas_pylibzfs = None

from middlewared.service import CallError


def create_dataset_with_pylibzfs(
    lz, name, dataset_type, properties, encryption_dict=None, create_ancestors=False
):
    """
    Create a ZFS dataset or volume using truenas_pylibzfs library.

    Args:
        lz: ZFS handle from thread local storage
        name: Full dataset name (e.g., 'pool/dataset')
        dataset_type: 'FILESYSTEM' or 'VOLUME'
        properties: Dictionary of ZFS properties to set
        encryption_dict: Optional dictionary with encryption configuration
        create_ancestors: Whether to create missing parent datasets

    Returns:
        None on success

    Raises:
        CallError: If dataset creation fails
    """
    try:
        # Determine ZFS type
        if dataset_type == "FILESYSTEM":
            zfs_type = truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM
        elif dataset_type == "VOLUME":
            zfs_type = truenas_pylibzfs.ZFSType.ZFS_TYPE_VOLUME
        else:
            raise CallError(f"Invalid dataset type: {dataset_type}")

        # Convert properties to truenas_pylibzfs format
        # The library expects property names as ZFSProperty enum values
        pylibzfs_props = {}
        user_props = {}

        # Map property names to ZFSProperty enum where applicable
        property_mapping = {
            "aclinherit": truenas_pylibzfs.ZFSProperty.ACLINHERIT,
            "aclmode": truenas_pylibzfs.ZFSProperty.ACLMODE,
            "acltype": truenas_pylibzfs.ZFSProperty.ACLTYPE,
            "atime": truenas_pylibzfs.ZFSProperty.ATIME,
            "casesensitivity": truenas_pylibzfs.ZFSProperty.CASESENSITIVITY,
            "checksum": truenas_pylibzfs.ZFSProperty.CHECKSUM,
            "compression": truenas_pylibzfs.ZFSProperty.COMPRESSION,
            "copies": truenas_pylibzfs.ZFSProperty.COPIES,
            "dedup": truenas_pylibzfs.ZFSProperty.DEDUP,
            "exec": truenas_pylibzfs.ZFSProperty.EXEC,
            "quota": truenas_pylibzfs.ZFSProperty.QUOTA,
            "readonly": truenas_pylibzfs.ZFSProperty.READONLY,
            "recordsize": truenas_pylibzfs.ZFSProperty.RECORDSIZE,
            "refquota": truenas_pylibzfs.ZFSProperty.REFQUOTA,
            "refreservation": truenas_pylibzfs.ZFSProperty.REFRESERVATION,
            "reservation": truenas_pylibzfs.ZFSProperty.RESERVATION,
            "snapdir": truenas_pylibzfs.ZFSProperty.SNAPDIR,
            "snapdev": truenas_pylibzfs.ZFSProperty.SNAPDEV,
            "sync": truenas_pylibzfs.ZFSProperty.SYNC,
            "volblocksize": truenas_pylibzfs.ZFSProperty.VOLBLOCKSIZE,
            "volsize": truenas_pylibzfs.ZFSProperty.VOLSIZE,
            "special_small_blocks": truenas_pylibzfs.ZFSProperty.SPECIAL_SMALL_BLOCKS,
        }

        # Process properties
        sparse = False
        # Determine keyformat early to handle pbkdf2iters correctly
        keyformat = None
        if encryption_dict:
            keyformat = encryption_dict.get("keyformat", "hex")

        for prop_name, prop_value in properties.items():
            # Skip encryption properties as they're handled separately
            if prop_name in ["encryption", "keyformat", "keylocation", "pbkdf2iters", "key"]:
                continue

            # Special handling for sparse - it's a creation option, not a property
            if prop_name == "sparse":
                sparse = prop_value
                continue

            # Check if it's a known ZFS property
            if prop_name in property_mapping:
                pylibzfs_props[property_mapping[prop_name]] = str(prop_value)
            # Check if it's a user property (contains ':')
            elif ":" in prop_name:
                user_props[prop_name] = str(prop_value)
            # Try to find the property by uppercase name
            else:
                try:
                    prop_enum = getattr(truenas_pylibzfs.ZFSProperty, prop_name.upper())
                    pylibzfs_props[prop_enum] = str(prop_value)
                except AttributeError:
                    # If not found, treat as user property
                    if prop_name not in ["sparse", "key"]:  # Skip known non-properties
                        user_props[prop_name] = str(prop_value)

        # Handle encryption if specified
        crypto_config = None
        if encryption_dict and encryption_dict.get("encryption") != "off":
            # keyformat was already determined above
            key = encryption_dict.get("key")
            if keyformat == "passphrase":
                crypto_config = lz.resource_cryptography_config(
                    keyformat="passphrase", key=key
                )
                # Add pbkdf2iters property for passphrase if specified
                if "pbkdf2iters" in encryption_dict:
                    pylibzfs_props[truenas_pylibzfs.ZFSProperty.PBKDF2ITERS] = str(
                        encryption_dict["pbkdf2iters"]
                    )
            else:
                crypto_config = lz.resource_cryptography_config(
                    keyformat="hex", key=key
                )

        # Create the dataset
        if create_ancestors:
            # If we need to create ancestors, we need to handle this differently
            # truenas_pylibzfs doesn't have a direct create_ancestors flag
            # So we'll create parent datasets first if needed
            for parent in reversed(pathlib.Path(name).parents):
                pp = parent.as_posix()
                if pp == "." or "/" not in pp:
                    # cwd or root dataset
                    continue
                try:
                    lz.create_resource(name=pp, type=truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM)
                except truenas_pylibzfs.ZFSException as e:
                    if e.code == truenas_pylibzfs.ZFSError.EZFS_EXISTS:
                        continue
                    else:
                        raise e from None

        # Now create the actual dataset
        # For volumes with sparse option, we need to handle it separately
        if dataset_type == "VOLUME" and sparse:
            # Sparse volumes are created by not setting reservation equal to volsize
            # This is handled automatically by the library when we don't set reservation
            pass

        # Create the dataset/volume
        if crypto_config:
            lz.create_resource(
                name=name,
                type=zfs_type,
                properties=pylibzfs_props,
                user_properties=user_props,
                crypto=crypto_config,
            )
        else:
            lz.create_resource(
                name=name,
                type=zfs_type,
                properties=pylibzfs_props,
                user_properties=user_props,
            )
    except Exception as e:
        raise CallError(f"Failed to create dataset {name}: {str(e)}")


def convert_properties_for_pylibzfs(properties):
    """
    Convert middleware property format to truenas_pylibzfs format.

    Args:
        properties: Dictionary with property names as strings

    Returns:
        Tuple of (zfs_properties, user_properties) suitable for pylibzfs
    """
    property_mapping = {
        "aclinherit": truenas_pylibzfs.ZFSProperty.ACLINHERIT,
        "aclmode": truenas_pylibzfs.ZFSProperty.ACLMODE,
        "acltype": truenas_pylibzfs.ZFSProperty.ACLTYPE,
        "atime": truenas_pylibzfs.ZFSProperty.ATIME,
        "casesensitivity": truenas_pylibzfs.ZFSProperty.CASESENSITIVITY,
        "checksum": truenas_pylibzfs.ZFSProperty.CHECKSUM,
        "compression": truenas_pylibzfs.ZFSProperty.COMPRESSION,
        "copies": truenas_pylibzfs.ZFSProperty.COPIES,
        "dedup": truenas_pylibzfs.ZFSProperty.DEDUP,
        "exec": truenas_pylibzfs.ZFSProperty.EXEC,
        "quota": truenas_pylibzfs.ZFSProperty.QUOTA,
        "readonly": truenas_pylibzfs.ZFSProperty.READONLY,
        "recordsize": truenas_pylibzfs.ZFSProperty.RECORDSIZE,
        "refquota": truenas_pylibzfs.ZFSProperty.REFQUOTA,
        "refreservation": truenas_pylibzfs.ZFSProperty.REFRESERVATION,
        "reservation": truenas_pylibzfs.ZFSProperty.RESERVATION,
        "snapdir": truenas_pylibzfs.ZFSProperty.SNAPDIR,
        "snapdev": truenas_pylibzfs.ZFSProperty.SNAPDEV,
        "sync": truenas_pylibzfs.ZFSProperty.SYNC,
        "volblocksize": truenas_pylibzfs.ZFSProperty.VOLBLOCKSIZE,
        "volsize": truenas_pylibzfs.ZFSProperty.VOLSIZE,
        "special_small_blocks": truenas_pylibzfs.ZFSProperty.SPECIAL_SMALL_BLOCKS,
    }

    zfs_props = {}
    user_props = {}

    for prop_name, prop_value in properties.items():
        if prop_name in property_mapping:
            zfs_props[property_mapping[prop_name]] = str(prop_value)
        elif ":" in prop_name:
            user_props[prop_name] = str(prop_value)

    return zfs_props, user_props
