import os

import pytest
from auto_config import pool_name
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.pool import another_pool
from middlewared.test.integration.utils import call, ssh

GiB = 1024**3


def destroy(path: str):
    call("zfs.resource.destroy", {"path": path, "recursive": True})


def test_zfs_resource_create_basic_filesystem():
    """Test basic filesystem creation returns the created entry and mounts it"""
    path = os.path.join(pool_name, "test_create_fs_basic")
    try:
        entry = call("zfs.resource.create", {"path": path})
        assert entry["name"] == path
        assert entry["pool"] == pool_name
        assert entry["type"] == "FILESYSTEM"

        result = call("zfs.resource.query", {"paths": [path], "properties": ["mounted", "xattr"]})
        assert len(result) == 1
        assert result[0]["properties"]["mounted"]["raw"] == "yes"
        # TrueNAS defaults xattr to sa on filesystems
        assert result[0]["properties"]["xattr"]["raw"] == "sa"
    finally:
        destroy(path)


def test_zfs_resource_create_with_properties():
    """Test that native property names are accepted and returned canonicalized"""
    path = os.path.join(pool_name, "test_create_fs_props")
    try:
        entry = call(
            "zfs.resource.create",
            {
                "path": path,
                "properties": {
                    "compression": "lz4",
                    "atime": "off",
                    "recordsize": "1M",
                },
            },
        )
        props = entry["properties"]
        assert props["compression"]["raw"] == "lz4"
        assert props["atime"]["raw"] == "off"
        # "1M" is canonicalized by ZFS to its byte value
        assert props["recordsize"]["value"] == 1024**2
    finally:
        destroy(path)


def test_zfs_resource_create_volume_thick_by_default():
    """Test volume creation is thick provisioned unless refreservation is given"""
    path = os.path.join(pool_name, "test_create_zvol_thick")
    try:
        entry = call(
            "zfs.resource.create",
            {"path": path, "type": "VOLUME", "properties": {"volsize": GiB}},
        )
        assert entry["type"] == "VOLUME"
        assert entry["properties"]["volsize"]["value"] == GiB
        assert entry["properties"]["refreservation"]["value"] == GiB
    finally:
        destroy(path)


def test_zfs_resource_create_volume_sparse():
    """Test sparse volume creation via refreservation=none"""
    path = os.path.join(pool_name, "test_create_zvol_sparse")
    try:
        entry = call(
            "zfs.resource.create",
            {
                "path": path,
                "type": "VOLUME",
                "properties": {"volsize": GiB, "refreservation": "none"},
            },
        )
        assert entry["type"] == "VOLUME"
        assert entry["properties"]["refreservation"]["value"] in (0, None)
    finally:
        destroy(path)


def test_zfs_resource_create_volume_capacity_guardrail():
    """Test that a thick volume reserving over 80% of the available space is
    rejected while a sparse volume of the same size is allowed"""
    avail = call("zfs.resource.query", {"paths": [pool_name], "properties": ["available"]})
    volsize = (int(avail[0]["properties"]["available"]["value"] * 0.9) // 16384) * 16384
    path = os.path.join(pool_name, "test_create_zvol_capacity")
    try:
        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.create",
                {"path": path, "type": "VOLUME", "properties": {"volsize": volsize}},
            )
        assert "create a sparse volume" in str(exc_info.value)

        entry = call(
            "zfs.resource.create",
            {
                "path": path,
                "type": "VOLUME",
                "properties": {"volsize": volsize, "refreservation": "none"},
            },
        )
        assert entry["properties"]["volsize"]["value"] == volsize
    finally:
        destroy(path)


def test_zfs_resource_create_volume_requires_volsize():
    """Test that creating a VOLUME without volsize fails"""
    path = os.path.join(pool_name, "test_create_zvol_novolsize")
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.create", {"path": path, "type": "VOLUME"})
    assert "volsize" in str(exc_info.value)


def test_zfs_resource_create_with_user_properties():
    """Test user properties are set at creation time"""
    path = os.path.join(pool_name, "test_create_fs_uprops")
    try:
        entry = call(
            "zfs.resource.create",
            {"path": path, "user_properties": {"org.test:canary": "value1"}},
        )
        assert entry["user_properties"]["org.test:canary"] == "value1"
    finally:
        destroy(path)


def test_zfs_resource_create_invalid_user_property_name():
    """Test that user property names without a colon are rejected"""
    path = os.path.join(pool_name, "test_create_fs_bad_uprop")
    with pytest.raises(Exception) as exc_info:
        call(
            "zfs.resource.create",
            {"path": path, "user_properties": {"nocolon": "value"}},
        )
    assert "colon" in str(exc_info.value).lower()


def test_zfs_resource_create_ancestors():
    """Test creating missing ancestors like `zfs create -p`"""
    root = os.path.join(pool_name, "test_create_anc")
    path = os.path.join(root, "a/b/c")
    try:
        entry = call("zfs.resource.create", {"path": path, "create_ancestors": True})
        assert entry["name"] == path

        result = call(
            "zfs.resource.query",
            {"paths": [root], "get_children": True, "properties": ["mounted"]},
        )
        assert len(result) == 4
        assert all(i["properties"]["mounted"]["raw"] == "yes" for i in result)
    finally:
        destroy(root)


def test_zfs_resource_create_missing_parent_fails():
    """Test that a missing parent without create_ancestors fails with a helpful message"""
    parent = os.path.join(pool_name, "test_create_noparent")
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.create", {"path": os.path.join(parent, "child")})
    emsg = str(exc_info.value)
    assert f"Parent dataset {parent!r} does not exist" in emsg
    assert "create_ancestors" in emsg


@pytest.mark.parametrize(
    "path,create_ancestors",
    [
        pytest.param("nonexistent_pool_xyz123/child", False, id="without create_ancestors"),
        # a deep path so the failure comes from ancestor creation
        pytest.param("nonexistent_pool_xyz123/a/b", True, id="with create_ancestors"),
    ],
)
def test_zfs_resource_create_missing_pool_fails(path, create_ancestors):
    """Test that a nonexistent pool fails with a clear message, with and without create_ancestors"""
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.create", {"path": path, "create_ancestors": create_ancestors})
    assert "Pool 'nonexistent_pool_xyz123' does not exist" in str(exc_info.value)


def test_zfs_resource_create_already_exists():
    """Test that creating an existing resource fails"""
    path = os.path.join(pool_name, "test_create_exists")
    try:
        call("zfs.resource.create", {"path": path})
        with pytest.raises(Exception) as exc_info:
            call("zfs.resource.create", {"path": path})
        assert "already exists" in str(exc_info.value).lower()
    finally:
        destroy(path)


@pytest.mark.parametrize(
    "path,error",
    [
        pytest.param("/tank/dataset", "absolute", id="absolute paths not allowed"),
        pytest.param("tank/dataset/", "forward-slash", id="trailing forward-slash not allowed"),
        pytest.param(
            "tank/dataset@snap",
            "zfs.resource.snapshot.create",
            id="snapshot paths not allowed",
        ),
        pytest.param("tank", "root filesystem", id="creating root filesystem not allowed"),
        pytest.param("boot-pool/test", "protected", id="protected paths not allowed"),
        pytest.param(
            "tank/dataset ",
            "not a valid ZFS resource name",
            id="trailing space not allowed",
        ),
    ],
)
def test_zfs_resource_create_validation_errors(path, error):
    """Test various path validation errors"""
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.create", {"path": path})
    assert error in str(exc_info.value)


@pytest.mark.parametrize(
    "prop",
    ["notaprop", "used", "canmount", "mountpoint", "logbias", "primarycache", "sparse"],
)
def test_zfs_resource_create_property_outside_allowed_set(prop):
    """Test that any property outside the allowed creation set is rejected"""
    path = os.path.join(pool_name, "test_create_fs_badprop")
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.create", {"path": path, "properties": {prop: "on"}})
    assert "may not be set at creation time" in str(exc_info.value)


def test_zfs_resource_create_property_invalid_for_type():
    """Test that volume-only properties are rejected on filesystems"""
    path = os.path.join(pool_name, "test_create_fs_volprop")
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.create", {"path": path, "properties": {"volsize": GiB}})
    assert "invalid for zfs type" in str(exc_info.value)


def test_zfs_resource_create_encryption_property_denied():
    """Test that encryption properties may not be set through generic properties"""
    path = os.path.join(pool_name, "test_create_fs_crypto")
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.create", {"path": path, "properties": {"encryption": "on"}})
    assert "may not be set through generic properties" in str(exc_info.value)


@pytest.mark.skip(reason="enable when the truenas.entitlements API is merged and the dedup license check is active")
def test_zfs_resource_create_dedup_requires_license():
    """Test that enabling deduplication requires the DEDUP license entitlement"""
    path = os.path.join(pool_name, "test_create_fs_dedup")
    if call("truenas.entitlements.check", "DEDUP")["entitled"]:
        try:
            entry = call("zfs.resource.create", {"path": path, "properties": {"dedup": "on"}})
            assert entry["properties"]["dedup"]["raw"] == "on"
        finally:
            destroy(path)
    else:
        with pytest.raises(Exception) as exc_info:
            call("zfs.resource.create", {"path": path, "properties": {"dedup": "on"}})
        assert "not licensed" in str(exc_info.value)


@pytest.mark.parametrize("prop", ["sharenfs", "sharesmb"])
def test_zfs_resource_create_sharing_property_denied(prop):
    """Test that ZFS native sharing properties may not be set through generic properties"""
    path = os.path.join(pool_name, "test_create_fs_sharing")
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.create", {"path": path, "properties": {prop: "on"}})
    emsg = str(exc_info.value)
    assert "may not be set through generic properties" in emsg
    assert "sharing.nfs" in emsg


def test_zfs_resource_create_encryption_root_with_key():
    """Test creating an encryption root with an explicit hex key; the key is stored by the system"""
    path = os.path.join(pool_name, "test_create_enc_key")
    key = "0123456789abcdef" * 4
    try:
        entry = call("zfs.resource.create", {"path": path, "encryption": {"key": key}})
        props = entry["properties"]
        assert props["encryption"]["raw"] != "off", props
        assert props["encryptionroot"]["raw"] == path, props
        assert props["keyformat"]["raw"] == "hex", props
        assert props["keystatus"]["raw"] == "available", props
        assert call("pool.dataset.export_key", path, job=True) == key
    finally:
        destroy(path)


def test_zfs_resource_create_encryption_root_generate_key():
    """Test creating an encryption root with a generated key retrievable via export_key"""
    path = os.path.join(pool_name, "test_create_enc_genkey")
    try:
        entry = call("zfs.resource.create", {"path": path, "encryption": {"generate_key": True}})
        assert entry["properties"]["keyformat"]["raw"] == "hex", entry["properties"]
        key = call("pool.dataset.export_key", path, job=True)
        assert len(key) == 64
        int(key, 16)  # valid hex
    finally:
        destroy(path)


def test_zfs_resource_create_encryption_root_passphrase():
    """Test creating a passphrase encryption root that the legacy lock flow can lock"""
    path = os.path.join(pool_name, "test_create_enc_pass")
    try:
        entry = call(
            "zfs.resource.create",
            {"path": path, "encryption": {"passphrase": "passphrase123"}},
        )
        props = entry["properties"]
        assert props["keyformat"]["raw"] == "passphrase", props
        assert props["encryptionroot"]["raw"] == path, props
        res = call("zfs.resource.query", {"paths": [path], "properties": ["pbkdf2iters"]})
        assert res[0]["properties"]["pbkdf2iters"]["value"] == 1300000, res[0]["properties"]
        assert call("pool.dataset.lock", path, job=True) is True
    finally:
        destroy(path)


@pytest.mark.parametrize(
    "encryption",
    [
        pytest.param({}, id="nothing provided"),
        pytest.param({"key": "0" * 64, "passphrase": "passphrase123"}, id="key and passphrase"),
        pytest.param(
            {"generate_key": True, "passphrase": "passphrase123"},
            id="generate_key and passphrase",
        ),
        pytest.param({"passphrase": "short"}, id="short passphrase"),
        pytest.param({"key": "notahexkey"}, id="invalid key"),
        pytest.param({"key": "0" * 63}, id="wrong key length"),
        pytest.param(
            {"passphrase": "passphrase123", "pbkdf2iters": 1000},
            id="pbkdf2iters too low",
        ),
        pytest.param(
            {"passphrase": "passphrase123", "pbkdf2iters": 100_000_000},
            id="pbkdf2iters too high",
        ),
    ],
)
def test_zfs_resource_create_encryption_shape_errors(encryption):
    """Test invalid encryption option combinations are rejected"""
    path = os.path.join(pool_name, "test_create_enc_invalid")
    with pytest.raises(ValidationErrors):
        call("zfs.resource.create", {"path": path, "encryption": encryption})


def test_zfs_resource_create_key_child_under_passphrase_parent():
    """Test that a key-encrypted root is denied beneath a passphrase parent while a
    passphrase root is allowed"""
    parent = os.path.join(pool_name, "test_create_pass_parent")
    call(
        "zfs.resource.create",
        {"path": parent, "encryption": {"passphrase": "passphrase123"}},
    )
    try:
        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.create",
                {"path": f"{parent}/keychild", "encryption": {"generate_key": True}},
            )
        assert "encrypted with a passphrase" in str(exc_info.value)

        child = f"{parent}/passchild"
        entry = call(
            "zfs.resource.create",
            {"path": child, "encryption": {"passphrase": "passphrase456"}},
        )
        assert entry["properties"]["encryptionroot"]["raw"] == child, entry["properties"]
    finally:
        destroy(parent)


def test_zfs_resource_create_encryption_sandwich_denied():
    """Test that an encryption root cannot be created beneath an unencrypted dataset
    that itself sits inside an encrypted one"""
    root = os.path.join(pool_name, "test_create_sandwich")
    key_file = "/tmp/test_create_sandwich.key"
    # enc -> unenc ancestry can only be built outside the API
    ssh(
        f"echo -n {'0' * 64} > {key_file} && "
        f"zfs create -o encryption=on -o keyformat=hex -o keylocation=file://{key_file} {root} && "
        f"zfs create -o encryption=off {root}/unenc"
    )
    try:
        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.create",
                {"path": f"{root}/unenc/child", "encryption": {"generate_key": True}},
            )
        assert "beneath an unencrypted dataset" in str(exc_info.value)
    finally:
        destroy(root)
        ssh(f"rm -f {key_file}")


def test_zfs_resource_create_under_encrypted_parent():
    """Test that a child of an encrypted parent inherits the encryption and
    that an unencrypted child cannot be created beneath it"""
    parent = os.path.join(pool_name, "test_create_enc_parent")
    call(
        "zfs.resource.create",
        {"path": parent, "encryption": {"passphrase": "passphrase123"}},
    )
    try:
        child = f"{parent}/child"
        call("zfs.resource.create", {"path": child})
        props = call("zfs.resource.query", {"paths": [child], "properties": ["encryption"]})[0]["properties"]
        assert props["encryption"]["raw"] != "off", props
        assert props["encryptionroot"]["raw"] == parent, props
        assert props["keystatus"]["raw"] == "available", props

        # the only way ZFS allows an unencrypted child (encryption=off) is denied
        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.create",
                {"path": f"{parent}/child2", "properties": {"encryption": "off"}},
            )
        assert "may not be set through generic properties" in str(exc_info.value)
    finally:
        destroy(parent)


def test_zfs_resource_create_under_locked_parent_fails():
    """Test that creating beneath a locked encrypted parent fails with a clear message"""
    parent = os.path.join(pool_name, "test_create_locked_parent")
    call(
        "zfs.resource.create",
        {"path": parent, "encryption": {"passphrase": "passphrase123"}},
    )
    try:
        call("pool.dataset.lock", parent, job=True)
        with pytest.raises(Exception) as exc_info:
            call("zfs.resource.create", {"path": f"{parent}/child"})
        emsg = str(exc_info.value)
        assert "encryption key is not loaded" in emsg
        assert "Unlock the parent dataset" in emsg
    finally:
        destroy(parent)


@pytest.fixture(scope="module")
def draid_pool():
    unused_disks = call("disk.get_unused")
    if len(unused_disks) < 2:
        pytest.skip("Insufficient number of unused disks for a dRAID pool")
    with another_pool(
        {
            "name": "test_zr_draid",
            "topology": {
                "data": [
                    {
                        "disks": [disk["name"] for disk in unused_disks[:2]],
                        "type": "DRAID1",
                        "draid_data_disks": 1,
                    }
                ],
            },
            "allow_duplicate_serials": True,
        }
    ) as pool:
        yield pool


def test_zfs_resource_create_draid_filesystem_recordsize_default(draid_pool):
    """Test that a filesystem on a dRAID pool defaults to a 1M recordsize"""
    path = f"{draid_pool['name']}/fs"
    call("zfs.resource.create", {"path": path})
    result = call("zfs.resource.query", {"paths": [path], "properties": ["recordsize"]})
    assert result[0]["properties"]["recordsize"]["value"] == 1024**2, result[0]["properties"]


def test_zfs_resource_create_draid_volume_volblocksize_default(draid_pool):
    """Test that a volume on a dRAID pool defaults to a 128K volblocksize"""
    path = f"{draid_pool['name']}/vol"
    call(
        "zfs.resource.create",
        {
            "path": path,
            "type": "VOLUME",
            "properties": {"volsize": 128 * 1024**2, "refreservation": "none"},
        },
    )
    result = call("zfs.resource.query", {"paths": [path], "properties": ["volblocksize"]})
    assert result[0]["properties"]["volblocksize"]["value"] == 128 * 1024, result[0]["properties"]


def test_zfs_resource_create_draid_volume_small_volblocksize_rejected(draid_pool):
    """Test that a volblocksize under 32K is rejected on a dRAID pool"""
    path = f"{draid_pool['name']}/vol_small"
    with pytest.raises(Exception) as exc_info:
        call(
            "zfs.resource.create",
            {
                "path": path,
                "type": "VOLUME",
                "properties": {
                    "volsize": 128 * 1024**2,
                    "volblocksize": "16K",
                    "refreservation": "none",
                },
            },
        )
    assert "32K" in str(exc_info.value)

    entry = call(
        "zfs.resource.create",
        {
            "path": path,
            "type": "VOLUME",
            "properties": {
                "volsize": 128 * 1024**2,
                "volblocksize": "32K",
                "refreservation": "none",
            },
        },
    )
    assert entry["properties"]["volblocksize"]["value"] == 32768, entry["properties"]


def test_zfs_resource_create_acl_normalization():
    """Test that an explicit acltype defaults the coupled acl properties"""
    path = os.path.join(pool_name, "test_create_fs_acl_posix")
    try:
        entry = call("zfs.resource.create", {"path": path, "properties": {"acltype": "posix"}})
        props = entry["properties"]
        assert props["acltype"]["raw"] == "posix", props
        assert props["aclmode"]["raw"] == "discard", props
        assert props["aclinherit"]["raw"] == "discard", props
    finally:
        destroy(path)

    path = os.path.join(pool_name, "test_create_fs_acl_nfsv4")
    try:
        entry = call(
            "zfs.resource.create",
            {
                "path": path,
                "properties": {"acltype": "nfsv4", "aclmode": "passthrough"},
            },
        )
        props = entry["properties"]
        assert props["acltype"]["raw"] == "nfsv4", props
        assert props["aclinherit"]["raw"] == "passthrough", props
    finally:
        destroy(path)


@pytest.mark.parametrize(
    "properties,error",
    [
        pytest.param(
            {"acltype": "nfsv4", "aclmode": "discard"},
            "nfsv4",
            id="nfsv4 with discard aclmode",
        ),
        pytest.param(
            {"acltype": "posix", "aclmode": "passthrough"},
            "posix or off",
            id="posix with non discard aclmode",
        ),
    ],
)
def test_zfs_resource_create_acl_invalid_combinations(properties, error):
    """Test that unusable acltype and aclmode combinations are rejected"""
    path = os.path.join(pool_name, "test_create_fs_acl_bad")
    with pytest.raises(Exception) as exc_info:
        call("zfs.resource.create", {"path": path, "properties": properties})
    assert error in str(exc_info.value)


def test_zfs_resource_create_acl_effective_from_parent():
    """Test that a missing acl property resolves from the nearest existing ancestor"""
    parent = os.path.join(pool_name, "test_create_acl_parent")
    call("zfs.resource.create", {"path": parent})
    try:
        # the parent's effective aclmode is the zfs default of discard
        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.create",
                {"path": f"{parent}/child", "properties": {"acltype": "nfsv4"}},
            )
        assert "nfsv4" in str(exc_info.value)

        # the parent's effective acltype is the zfs default of off
        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.create",
                {"path": f"{parent}/child", "properties": {"aclmode": "passthrough"}},
            )
        assert "posix or off" in str(exc_info.value)
    finally:
        destroy(parent)

    parent = os.path.join(pool_name, "test_create_acl_parent_nfsv4")
    call(
        "zfs.resource.create",
        {"path": parent, "properties": {"acltype": "nfsv4", "aclmode": "passthrough"}},
    )
    try:
        entry = call(
            "zfs.resource.create",
            {"path": f"{parent}/child", "properties": {"acltype": "nfsv4"}},
        )
        assert entry["properties"]["aclinherit"]["raw"] == "passthrough", entry["properties"]
    finally:
        destroy(parent)


def test_zfs_resource_create_under_readonly_parent_fails():
    """Test that creating beneath a readonly parent is refused up front"""
    parent = os.path.join(pool_name, "test_create_ro_parent")
    call("zfs.resource.create", {"path": parent, "properties": {"readonly": "on"}})
    try:
        with pytest.raises(Exception) as exc_info:
            call("zfs.resource.create", {"path": f"{parent}/child"})
        assert f"Turn off readonly mode on {parent!r}" in str(exc_info.value)

        # the nearest existing ancestor is checked when creating ancestors too
        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.create",
                {"path": f"{parent}/a/b", "create_ancestors": True},
            )
        assert "readonly" in str(exc_info.value)
    finally:
        destroy(parent)


def test_zfs_resource_create_ssb_behavior_without_tiering():
    """Test special_small_blocks passthrough, volume pinning and filesystem
    inheritance while tiering is disabled"""
    if call("zfs.tier.config")["enabled"]:
        pytest.skip("ZFS tiering is enabled on this system")

    parent = os.path.join(pool_name, "test_create_ssb_parent")
    # explicit special_small_blocks passes straight through to zfs
    entry = call(
        "zfs.resource.create",
        {"path": parent, "properties": {"special_small_blocks": "128K"}},
    )
    assert entry["properties"]["special_small_blocks"]["value"] == 128 * 1024, entry["properties"]
    try:
        # a volume with blocks under the parent threshold is pinned to zero
        vol = f"{parent}/vol"
        call(
            "zfs.resource.create",
            {
                "path": vol,
                "type": "VOLUME",
                "properties": {"volsize": 128 * 1024**2, "refreservation": "none"},
            },
        )
        result = call(
            "zfs.resource.query",
            {
                "paths": [vol],
                "properties": ["special_small_blocks"],
                "get_source": True,
            },
        )
        prop = result[0]["properties"]["special_small_blocks"]
        assert prop["value"] in (0, None), prop
        assert prop["source"]["type"] == "LOCAL", prop

        # a volume with blocks at the threshold inherits as usual
        vol2 = f"{parent}/vol2"
        call(
            "zfs.resource.create",
            {
                "path": vol2,
                "type": "VOLUME",
                "properties": {
                    "volsize": 128 * 1024**2,
                    "volblocksize": "128K",
                    "refreservation": "none",
                },
            },
        )
        result = call(
            "zfs.resource.query",
            {
                "paths": [vol2],
                "properties": ["special_small_blocks"],
                "get_source": True,
            },
        )
        prop = result[0]["properties"]["special_small_blocks"]
        assert prop["value"] == 128 * 1024, prop
        assert prop["source"]["type"] == "INHERITED", prop

        # a filesystem is not pinned when tiering is disabled
        fs = f"{parent}/fs"
        call("zfs.resource.create", {"path": fs})
        result = call(
            "zfs.resource.query",
            {"paths": [fs], "properties": ["special_small_blocks"], "get_source": True},
        )
        prop = result[0]["properties"]["special_small_blocks"]
        assert prop["source"]["type"] == "INHERITED", prop
    finally:
        destroy(parent)


@pytest.fixture(scope="module")
def tier_pool():
    if not call("system.is_enterprise"):
        pytest.skip("ZFS tiering requires an Enterprise license")
    unused_disks = call("disk.get_unused")
    if len(unused_disks) < 6:
        pytest.skip("Need at least 6 unused disks for a tier pool")
    with another_pool(
        {
            "topology": {
                "data": [{"type": "RAIDZ1", "disks": [d["name"] for d in unused_disks[:3]]}],
                "special": [{"type": "RAIDZ1", "disks": [d["name"] for d in unused_disks[3:6]]}],
            },
            "allow_duplicate_serials": True,
        }
    ) as pool:
        original = call("zfs.tier.config")
        call("zfs.tier.update", {"enabled": True})
        try:
            yield pool["name"]
        finally:
            call("zfs.tier.update", {"enabled": original["enabled"]})


def test_zfs_resource_create_tier_managed_ssb_denied(tier_pool):
    """Test that special_small_blocks is rejected while tiering is enabled"""
    with pytest.raises(Exception) as exc_info:
        call(
            "zfs.resource.create",
            {"path": f"{tier_pool}/x", "properties": {"special_small_blocks": "64K"}},
        )
    assert "zfs.tier.dataset_set_tier" in str(exc_info.value)


def test_zfs_resource_create_tier_snaps_filesystem_placement(tier_pool):
    """Test that a new filesystem is pinned to its parent's effective tier"""
    # the pool root is REGULAR so the child pins to zero
    fs = f"{tier_pool}/tier_fs"
    call("zfs.resource.create", {"path": fs})
    result = call(
        "zfs.resource.query",
        {"paths": [fs], "properties": ["special_small_blocks"], "get_source": True},
    )
    prop = result[0]["properties"]["special_small_blocks"]
    assert prop["value"] in (0, None), prop
    assert prop["source"]["type"] == "LOCAL", prop

    # a PERFORMANCE parent pins the child to 16M
    ssh(f"zfs set special_small_blocks=16M {fs}")
    child = f"{fs}/child"
    call("zfs.resource.create", {"path": child})
    result = call(
        "zfs.resource.query",
        {"paths": [child], "properties": ["special_small_blocks"], "get_source": True},
    )
    prop = result[0]["properties"]["special_small_blocks"]
    assert prop["value"] == 16 * 1024**2, prop
    assert prop["source"]["type"] == "LOCAL", prop


def test_zfs_resource_create_tier_dedup_denied_on_performance(tier_pool):
    """Test that dedup is rejected beneath a PERFORMANCE parent but allowed on REGULAR"""
    parent = f"{tier_pool}/dedup_parent"
    call("zfs.resource.create", {"path": parent})
    ssh(f"zfs set special_small_blocks=16M {parent}")
    with pytest.raises(Exception) as exc_info:
        call(
            "zfs.resource.create",
            {"path": f"{parent}/child", "properties": {"dedup": "on"}},
        )
    assert "PERFORMANCE tier" in str(exc_info.value)

    entry = call(
        "zfs.resource.create",
        {"path": f"{tier_pool}/dedup_ok", "properties": {"dedup": "on"}},
    )
    assert entry["properties"]["dedup"]["raw"] == "on", entry["properties"]
