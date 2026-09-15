"""S3 buckets: a dataset this plugin creates and registers with the S3
service, with its access grants embedded. Creating, dropping, enabling
or disabling a bucket and changing the owner, the grants or the audit
mask apply on a reload; changing a field consumed at registration,
such as the ETag mode, restarts the service."""

import contextlib
import hashlib
import os
import re
import tempfile
from configparser import RawConfigParser

import pytest
from middlewared.service_exception import CallError, ValidationErrors
from middlewared.test.integration.assets.account import unprivileged_user_client, user
from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.assets.pool import dataset, pool
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server
from truenas_api_client import ValidationErrors as ClientValidationErrors

SERVICE = "s3"
BUCKETS_CONF = "/etc/truenas_s3/buckets.conf"
POLICIES_CONF = "/etc/truenas_s3/policies.conf"
OWNER = "s3bucketowner"
DATASET = f"{pool}/s3-bucket-test"


def parse(path):
    parser = RawConfigParser(interpolation=None)
    parser.read_string(ssh(f"cat {path}"))
    return {section: dict(parser[section]) for section in parser.sections()}


def service():
    return call("service.query", [["service", "=", SERVICE]], {"get": True})


def zfs_props(name, props):
    rows = call("zfs.resource.query", {"paths": [name], "properties": props})
    return {p: rows[0]["properties"][p]["raw"] for p in props} if rows else None


@contextlib.contextmanager
def running_service():
    assert call("service.control", "START", SERVICE, {"silent": False}, job=True)
    try:
        yield
    finally:
        call("service.control", "STOP", SERVICE, {"silent": False}, job=True)


@pytest.fixture
def versioning_licensed():
    with entitled("S3_VERSIONING"):
        yield


@pytest.fixture(scope="module")
def owner():
    with user(
        {
            "username": OWNER,
            "full_name": "bucket owner",
            "group_create": True,
            "password": "test1234",
        }
    ) as u:
        yield u


@contextlib.contextmanager
def bucket(**overrides):
    data = {"name": "test-bucket", "dataset": DATASET, "owner": OWNER, **overrides}
    entry = call("sharing.s3.create", data)
    try:
        yield entry
    finally:
        with contextlib.suppress(Exception):
            call("sharing.s3.delete", entry["id"])
        # the bucket keeps its dataset; the test does not
        call("zfs.resource.destroy", {"path": entry["dataset"], "recursive": True})


def test_create_owns_the_dataset(owner):
    """The dataset is created with every property the S3 on-disk format
    requires, the bucket holds the owner's uid, the row renders at the
    dataset's mount point without storing it, and the share root is the
    daemon's to make: absent until the service starts, then the owner's.
    Under the default `BUCKET_OWNER_ENFORCED` that tree is owner-only:
    `0700`, group `0`."""
    with bucket() as b:
        assert "path" not in b
        assert b["owner"] == OWNER
        assert b["owner_uid"] == owner["uid"]
        assert b["enabled"] is True
        assert b["grants"] == []
        assert b["locked"] is False
        assert zfs_props(
            DATASET,
            [
                "casesensitivity",
                "normalization",
                "utf8only",
                "xattr",
                "acltype",
                "aclmode",
                "aclinherit",
            ],
        ) == {
            "casesensitivity": "sensitive",
            "normalization": "none",
            "utf8only": "off",
            "xattr": "sa",
            "acltype": "nfsv4",
            "aclmode": "restricted",
            "aclinherit": "passthrough",
        }

        root = call("filesystem.stat", f"/mnt/{DATASET}")
        assert (root["uid"], root["gid"]) == (0, 0), "the dataset root stays the daemon's"
        assert ssh(f"test -e /mnt/{DATASET}/s3data || echo absent").strip() == "absent"
        with running_service():
            data = call("filesystem.stat", f"/mnt/{DATASET}/s3data")
            assert (data["uid"], data["gid"]) == (owner["uid"], 0)
            assert data["mode"] & 0o777 == 0o700

        call("etc.generate", "truenas_s3")
        row = parse(BUCKETS_CONF)['bucket "test-bucket"']
        assert row == {
            "dataset": DATASET,
            "path": f"/mnt/{DATASET}",
            "owner": OWNER,
            "owner_id": str(owner["uid"]),
            "permissions_model": "s3",
            "object_ownership": "bucket_owner_enforced",
            "versioning": "off",
            "multipart_etag": "composite",
            "object_lock": "off",
        }

    assert zfs_props(DATASET, ["mountpoint"]) is None


def test_object_writer_share_root_is_provisioned_once(owner):
    """Under `OBJECT_WRITER` the share root is created once, as the
    owner and their primary group at `0755`; a later start leaves an
    existing tree as found, so an operator's rechown stands."""
    with bucket(object_ownership="OBJECT_WRITER"):
        with running_service():
            data = call("filesystem.stat", f"/mnt/{DATASET}/s3data")
            assert (data["uid"], data["gid"]) == (owner["uid"], owner["group"]["bsdgrp_gid"])
            assert data["mode"] & 0o777 == 0o755
        ssh(f"chown 0:0 /mnt/{DATASET}/s3data")
        with running_service():
            data = call("filesystem.stat", f"/mnt/{DATASET}/s3data")
            assert (data["uid"], data["gid"]) == (0, 0), "an existing tree is left exactly as found"


def test_delete_keeps_the_dataset(owner):
    entry = call("sharing.s3.create", {"name": "keeps-data", "dataset": DATASET, "owner": OWNER})
    try:
        with running_service():
            ssh(f"touch /mnt/{DATASET}/s3data/marker")
        call("sharing.s3.delete", entry["id"])
        assert not call("sharing.s3.query", [["id", "=", entry["id"]]])
        assert zfs_props(DATASET, ["mounted"]) == {"mounted": "yes"}
        assert ssh(f"ls -A /mnt/{DATASET}").split() == [".truenas_s3", "s3data"]
        assert ssh(f"ls /mnt/{DATASET}/s3data").split() == ["marker"]
        call("etc.generate", "truenas_s3")
        assert 'bucket "keeps-data"' not in parse(BUCKETS_CONF)
    finally:
        call("zfs.resource.destroy", {"path": DATASET, "recursive": True})


@contextlib.contextmanager
def managed_root(value):
    """Set `value` as the S3 service's managed root, then restore the old
    value. A bucket created without a `dataset` goes under this root."""
    was = call("s3.config")["managed_root_dataset"]
    call("s3.update", {"managed_root_dataset": value})
    try:
        yield value
    finally:
        call("s3.update", {"managed_root_dataset": was})


def test_a_bucket_with_no_dataset_lands_under_the_managed_root(owner):
    """An S3 client sends only a bucket name, so the service selects the
    dataset."""
    with dataset("s3-managed-root") as root, managed_root(root):
        entry = call("sharing.s3.create", {"name": "derived", "owner": OWNER})
        try:
            assert entry["dataset"] == f"{root}/derived"
            # the derived dataset is the bucket's own, with the same
            # properties an explicitly named one gets
            assert zfs_props(entry["dataset"], ["xattr", "acltype"]) == {
                "xattr": "sa",
                "acltype": "nfsv4",
            }
        finally:
            call("sharing.s3.delete", entry["id"])


def test_a_recreated_bucket_does_not_land_on_the_old_data(owner):
    """`sharing.s3.delete` keeps the dataset and its objects. A second
    bucket with the same name must get a new dataset. If it does not, it
    serves the objects of the first bucket."""
    with dataset("s3-managed-reuse") as root, managed_root(root):
        first = call("sharing.s3.create", {"name": "recycled", "owner": OWNER})
        assert first["dataset"] == f"{root}/recycled"
        call("sharing.s3.delete", first["id"])
        assert zfs_props(first["dataset"], ["mountpoint"]) is not None, "the dataset is kept"

        second = call("sharing.s3.create", {"name": "recycled", "owner": OWNER})
        try:
            assert second["dataset"] == f"{root}/recycled_1"
        finally:
            call("sharing.s3.delete", second["id"])


def test_no_managed_root_refuses_a_bucket_with_no_dataset(owner):
    with managed_root(""):
        with pytest.raises(ValidationErrors) as ve:
            call("sharing.s3.create", {"name": "nowhere", "owner": OWNER})
        assert "dataset" in ve.value.errors[0].attribute
        assert not call("sharing.s3.query", [["name", "=", "nowhere"]])


def test_the_managed_root_must_exist():
    with pytest.raises(ValidationErrors) as ve:
        call("s3.update", {"managed_root_dataset": f"{pool}/s3-no-such-root"})
    assert "managed_root_dataset" in ve.value.errors[0].attribute
    assert call("s3.config")["managed_root_dataset"] != f"{pool}/s3-no-such-root"


def test_existing_dataset_is_refused(owner):
    with dataset("s3-preexisting") as ds:
        with pytest.raises(ValidationErrors):
            call("sharing.s3.create", {"name": "adopt-me", "dataset": ds, "owner": OWNER})
        assert not call("sharing.s3.query", [["name", "=", "adopt-me"]])


@pytest.mark.parametrize(
    "name",
    ["UPPER", "ab", "a..b", "192.168.1.1", "-lead", "trail-"],
)
def test_bad_names_are_refused(owner, name):
    with pytest.raises(ValidationErrors):
        call("sharing.s3.create", {"name": name, "dataset": DATASET, "owner": OWNER})


@pytest.mark.parametrize("name", ["999.1.1.1", "192.168.001.001"])
def test_a_name_that_merely_looks_numeric_is_allowed(owner, name):
    # not IPv4 addresses to the standard parser (999 is no octet; leading
    # zeros are RFC 3986 reg-names) — middleware and the S3 service both
    # use it, so the two vocabularies agree
    with bucket(name=name):
        call("etc.generate", "truenas_s3")
        assert f'bucket "{name}"' in parse(BUCKETS_CONF)


def test_unknown_owner_is_refused():
    with pytest.raises(ValidationErrors) as ve:
        call(
            "sharing.s3.create",
            {"name": "no-owner", "dataset": DATASET, "owner": "nosuchuser"},
        )
    assert "does not exist" in ve.value.errors[0].errmsg
    assert zfs_props(DATASET, ["mountpoint"]) is None, "nothing was created"


def test_root_may_not_own_a_bucket(owner):
    """The owner bypasses the bucket's grants and owns every object written
    under `BUCKET_OWNER_ENFORCED`, and uid 0 is an owner the filesystem
    does not restrain either. Refused on both paths that set one."""
    with pytest.raises(ValidationErrors) as ve:
        call(
            "sharing.s3.create",
            {"name": "root-owned", "dataset": DATASET, "owner": "root"},
        )
    assert "owner" in ve.value.errors[0].attribute
    assert zfs_props(DATASET, ["mountpoint"]) is None, "nothing was created"

    with bucket() as b:
        with pytest.raises(ValidationErrors) as ve:
            call("sharing.s3.update", b["id"], {"owner": "root"})
        assert "owner" in ve.value.errors[0].attribute
        assert call("sharing.s3.get_instance", b["id"])["owner"] == OWNER


def test_grants_live_on_the_bucket(owner):
    grants = [
        {"principal_type": "USER", "xid": owner["uid"], "access": "READWRITE"},
        {"principal_type": "EVERYONE", "access": "READONLY"},
    ]
    with bucket(grants=grants) as b:
        assert [g["name"] for g in b["grants"]] == [OWNER, ""]
        call("etc.generate", "truenas_s3")
        assert parse(POLICIES_CONF) == {
            f'grant user "{OWNER}" "test-bucket"': {
                "xid": str(owner["uid"]),
                "access": "readwrite",
            },
            'grant everyone "test-bucket"': {"access": "readonly"},
        }

        # the list is replaced whole
        updated = call(
            "sharing.s3.update",
            b["id"],
            {"grants": [{"principal_type": "EVERYONE", "access": "DENY"}]},
        )
        assert [g["access"] for g in updated["grants"]] == ["DENY"]
        call("etc.generate", "truenas_s3")
        assert parse(POLICIES_CONF) == {'grant everyone "test-bucket"': {"access": "deny"}}

        for bad, message in (
            (
                [{"principal_type": "EVERYONE", "xid": 5, "access": "READONLY"}],
                "not allowed",
            ),
            ([{"principal_type": "GROUP", "access": "READONLY"}], "required"),
            (
                [{"principal_type": "GROUP", "xid": 4294967000, "access": "READONLY"}],
                "No group",
            ),
            (grants + [grants[0]], "only be granted once"),
        ):
            with pytest.raises(ValidationErrors) as ve:
                call("sharing.s3.update", b["id"], {"grants": bad})
            assert message in ve.value.errors[0].errmsg

    # the grants died with the bucket
    call("etc.generate", "truenas_s3")
    assert parse(POLICIES_CONF) == {}


def test_object_ownership_is_its_own_key(owner):
    """`permissions_model` and `object_ownership` are one axis each: the
    first says how the S3 service treats the filesystem permissions on
    the tree, the second which account an S3 operation runs as and
    whether the bucket supports S3 ACLs. A shared tree folds to the one
    uid it can run as."""
    with bucket() as b:
        assert (b["permissions_model"], b["object_ownership"]) == ("S3", "BUCKET_OWNER_ENFORCED")
        call("etc.generate", "truenas_s3")
        row = parse(BUCKETS_CONF)['bucket "test-bucket"']
        assert (row["permissions_model"], row["object_ownership"]) == ("s3", "bucket_owner_enforced")

        updated = call("sharing.s3.update", b["id"], {"object_ownership": "BUCKET_OWNER_PREFERRED"})
        assert (updated["permissions_model"], updated["object_ownership"]) == ("S3", "BUCKET_OWNER_PREFERRED")
        call("etc.generate", "truenas_s3")
        assert parse(BUCKETS_CONF)['bucket "test-bucket"']["object_ownership"] == "bucket_owner_preferred"

        # a shared tree runs as the caller whatever it is given: the other
        # protocols' users own the filesystem permissions there
        updated = call(
            "sharing.s3.update",
            b["id"],
            {"permissions_model": "MULTIPROTOCOL", "object_ownership": "BUCKET_OWNER_ENFORCED"},
        )
        assert (updated["permissions_model"], updated["object_ownership"]) == ("MULTIPROTOCOL", "OBJECT_WRITER")
        call("etc.generate", "truenas_s3")
        row = parse(BUCKETS_CONF)['bucket "test-bucket"']
        assert (row["permissions_model"], row["object_ownership"]) == ("multiprotocol", "object_writer")

        # leaving the shared model must name the ownership: the stored
        # OBJECT_WRITER fold would otherwise take effect and enable ACLs
        with pytest.raises(ValidationErrors) as ve:
            call("sharing.s3.update", b["id"], {"permissions_model": "S3"})
        assert "object_ownership" in ve.value.errors[0].attribute
        updated = call(
            "sharing.s3.update",
            b["id"],
            {"permissions_model": "S3", "object_ownership": "BUCKET_OWNER_ENFORCED"},
        )
        assert (updated["permissions_model"], updated["object_ownership"]) == ("S3", "BUCKET_OWNER_ENFORCED")


def test_versioning_requires_a_license(owner):
    with entitled("S3_VERSIONING", False):
        with pytest.raises(ValidationErrors) as ve:
            call(
                "sharing.s3.create",
                {"name": "versioned", "dataset": DATASET, "owner": OWNER, "versioning": "ENABLED"},
            )
        assert ve.value.errors[0].attribute == "sharing_s3_create.versioning"
        assert "S3 object versioning" in ve.value.errors[0].errmsg


def test_object_lock_rules(owner, versioning_licensed):
    for bad, field in (
        ({"object_lock": True}, "versioning"),
        (
            {
                "object_lock": True,
                "versioning": "ENABLED",
                "permissions_model": "MULTIPROTOCOL",
            },
            "permissions_model",
        ),
        (
            {"object_lock_default_mode": "GOVERNANCE", "object_lock_default_days": 30},
            "object_lock",
        ),
        (
            {
                "object_lock": True,
                "versioning": "ENABLED",
                "object_lock_default_days": 30,
            },
            "object_lock_default_mode",
        ),
        (
            {
                "object_lock": True,
                "versioning": "ENABLED",
                "object_lock_default_days": 36501,
            },
            "object_lock_default_days",
        ),
    ):
        with pytest.raises(ValidationErrors) as ve:
            call(
                "sharing.s3.create",
                {"name": "locked", "dataset": DATASET, "owner": OWNER, **bad},
            )
        assert field in ve.value.errors[0].attribute

    # the period is days, however long: the daemon's years are 365 days
    # each, so the one field spells every rule it could. Only a shared
    # tree may not carry a lock, whatever the bucket's object ownership
    with bucket(
        name="locked",
        versioning="ENABLED",
        object_ownership="OBJECT_WRITER",
        object_lock=True,
        object_lock_default_mode="COMPLIANCE",
        object_lock_default_days=365,
    ):
        call("etc.generate", "truenas_s3")
        row = parse(BUCKETS_CONF)['bucket "locked"']
        assert row["permissions_model"] == "s3"
        assert row["object_ownership"] == "object_writer"
        assert row["versioning"] == "enabled"
        assert row["object_lock"] == "enabled"
        assert row["object_lock_default_mode"] == "compliance"
        assert row["object_lock_default_days"] == "365"
        assert "object_lock_default_years" not in row


def test_the_one_way_fields_hold(owner, versioning_licensed):
    """Object lock and versioning move one way. The dataset root's lock
    latch never lowers and the S3 service refuses to serve a row that
    contradicts it, so disabling the lock would only take the bucket out
    of service; and a versioned bucket has no way back to OFF — its
    stored versions would go unreachable."""
    with bucket(name="one-way", versioning="ENABLED", object_lock=True) as b:
        for change, field in (
            ({"object_lock": False}, "object_lock"),
            ({"versioning": "OFF"}, "versioning"),
        ):
            with pytest.raises(ValidationErrors) as ve:
                call("sharing.s3.update", b["id"], change)
            assert field in ve.value.errors[0].attribute

    # an unlocked bucket may suspend, which keeps its versions; OFF is
    # refused there too, and the refusal names the destructive escape
    # hatch
    with bucket(name="one-way", versioning="ENABLED") as b:
        assert call("sharing.s3.update", b["id"], {"versioning": "SUSPENDED"})["versioning"] == "SUSPENDED"
        with pytest.raises(ValidationErrors) as ve:
            call("sharing.s3.update", b["id"], {"versioning": "OFF"})
        assert "versioning" in ve.value.errors[0].attribute
        assert "force_disable_versioning" in ve.value.errors[0].errmsg


NFS4_DACL = [
    {"tag": tag, "id": -1, "type": "ALLOW", "perms": {"BASIC": basic}, "flags": {"BASIC": "INHERIT"}}
    for tag, basic in (("owner@", "FULL_CONTROL"), ("everyone@", "READ"))
]


def permissions_change(method, path, uid=0, **options):
    """The `method` permissions change on `path`, each with a payload that is
    otherwise valid for an NFSv4 dataset, so that only the path and the
    options decide whether it is refused."""
    data = {"path": path, "options": options}
    match method:
        case "filesystem.chown":
            data["uid"] = uid
        case "filesystem.setperm":
            data["mode"] = "755"
            data["options"]["stripacl"] = True
        case "filesystem.setacl":
            data["dacl"] = NFS4_DACL
            data["options"]["validate_effective_acl"] = False
    return call(method, data, job=True)


def test_recursive_permissions_changes_stop_at_the_bucket(owner):
    """A recursive change over the whole bucket is refused, whether it targets
    the mountpoint of the bucket's dataset or traverses into it from above,
    and points at the bucket's `s3data` directory instead. The same change on
    that directory, and a non-recursive one on the mountpoint, go through."""
    with dataset("s3-perm-parent", {"share_type": "SMB"}) as parent, bucket(dataset=f"{parent}/inner") as b:
        mountpoint = f"/mnt/{b['dataset']}"
        for method in ("filesystem.chown", "filesystem.setperm", "filesystem.setacl"):
            with pytest.raises(ClientValidationErrors) as ve:
                permissions_change(method, mountpoint, recursive=True)
            (error,) = ve.value.errors
            assert error.attribute == f"{method}.path", method
            assert b["name"] in error.errmsg, method
            assert f"{mountpoint}/s3data" in error.errmsg, method

            with pytest.raises(ClientValidationErrors) as ve:
                permissions_change(method, f"/mnt/{parent}", recursive=True, traverse=True)
            (error,) = ve.value.errors
            assert error.attribute == f"{method}.options.traverse", method
            assert b["name"] in error.errmsg, method
            assert "s3data" in error.errmsg, method

        with running_service():
            permissions_change("filesystem.chown", f"{mountpoint}/s3data", uid=owner["uid"], recursive=True)
            permissions_change("filesystem.chown", mountpoint)
            # the parent is no bucket, and without traverse the recursion stops at its edge
            permissions_change("filesystem.chown", f"/mnt/{parent}", recursive=True)


def test_registry_changes_reload_and_consumed_fields_restart(owner):
    """Creating, disabling, enabling and dropping a bucket, and a grant
    change, keep the service's pid (a reload); changing a field consumed
    at registration — the ETag mode here — restarts it."""
    assert call("service.control", "START", SERVICE, {"silent": False}, job=True)
    try:
        pid = service()["pids"]
        with bucket() as b:
            assert service()["pids"] == pid, "registering a bucket is a reload"
            assert 'bucket "test-bucket"' in parse(BUCKETS_CONF)

            call(
                "sharing.s3.update",
                b["id"],
                {"grants": [{"principal_type": "EVERYONE", "access": "READONLY"}]},
            )
            assert service()["pids"] == pid, "a grant change is a reload"

            call("sharing.s3.update", b["id"], {"multipart_etag": "MINTED"})
            after_etag = service()["pids"]
            assert after_etag != pid, "the ETag mode is registered, so a restart"

            call("sharing.s3.update", b["id"], {"enabled": False})
            assert service()["pids"] == after_etag, "disabling a bucket is a reload"
            assert 'bucket "test-bucket"' not in parse(BUCKETS_CONF)

            call("sharing.s3.update", b["id"], {"enabled": True})
            assert service()["pids"] == after_etag, "enabling a bucket is a reload"
            assert 'bucket "test-bucket"' in parse(BUCKETS_CONF)
        assert service()["pids"] == after_etag, "dropping a bucket is a reload"
        assert service()["state"] == "RUNNING"
    finally:
        call("service.control", "STOP", SERVICE, {"silent": False}, job=True)


def test_destroying_the_dataset_deregisters_the_bucket(owner):
    entry = call("sharing.s3.create", {"name": "doomed", "dataset": DATASET, "owner": OWNER})
    assert call("pool.dataset.attachments", entry["dataset"]) == [
        {"type": "S3 Bucket", "service": SERVICE, "attachments": ["doomed"]}
    ]
    call("pool.dataset.delete", entry["dataset"])
    assert not call("sharing.s3.query", [["id", "=", entry["id"]]])
    assert zfs_props(DATASET, ["mountpoint"]) is None


def test_owner_change_reattaches_an_enforced_bucket(owner):
    """Under the default `BUCKET_OWNER_ENFORCED` an owner change is a
    reload: the new owner lands in the render and the daemon moves the
    owner-only share root to the new account."""
    with (
        user(
            {
                "username": "s3newowner",
                "full_name": "new owner",
                "group_create": True,
                "password": "test1234",
            }
        ) as new,
        bucket() as b,
        running_service(),
    ):
        pid = service()["pids"]
        updated = call("sharing.s3.update", b["id"], {"owner": "s3newowner"})
        assert updated["owner_uid"] == new["uid"]
        assert service()["pids"] == pid, "an owner change is a reload"
        data = call("filesystem.stat", f"/mnt/{DATASET}/s3data")
        assert (data["uid"], data["gid"]) == (new["uid"], 0), "the share root moves to the new owner"
        call("etc.generate", "truenas_s3")
        row = parse(BUCKETS_CONF)['bucket "test-bucket"']
        assert (row["owner"], row["owner_id"]) == ("s3newowner", str(new["uid"]))

        # the name is resolved from the uid on every read, never stored
        call("user.update", new["id"], {"username": "s3renamedowner"})
        assert call("sharing.s3.get_instance", b["id"])["owner"] == "s3renamedowner"
        assert call("sharing.s3.query", [["owner_uid", "=", new["uid"]]], {"get": True})["owner"] == "s3renamedowner"
        call("etc.generate", "truenas_s3")
        row = parse(BUCKETS_CONF)['bucket "test-bucket"']
        assert (row["owner"], row["owner_id"]) == ("s3renamedowner", str(new["uid"]))
        # naming the same account again is not a change of owner
        assert call("sharing.s3.update", b["id"], {"owner": "s3renamedowner"})["owner_uid"] == new["uid"]


def test_owner_change_leaves_a_shared_directory_as_found(owner):
    """Under `OBJECT_WRITER` an owner change is a reload and leaves the
    share root's ownership and mode untouched."""
    with (
        user(
            {
                "username": "s3newowner",
                "full_name": "new owner",
                "group_create": True,
                "password": "test1234",
            }
        ) as new,
        bucket(object_ownership="OBJECT_WRITER") as b,
        running_service(),
    ):
        pid = service()["pids"]
        assert call("sharing.s3.update", b["id"], {"owner": "s3newowner"})["owner_uid"] == new["uid"]
        assert service()["pids"] == pid, "an owner change is a reload"
        data = call("filesystem.stat", f"/mnt/{DATASET}/s3data")
        assert (data["uid"], data["gid"]) == (owner["uid"], owner["group"]["bsdgrp_gid"])
        assert data["mode"] & 0o777 == 0o755


def test_audit_choices():
    choices = call("sharing.s3.audit_choices")
    # the S3 service's maskable vocabulary in full: every grantable
    # action plus the bucket plane, minus the bypass probe
    assert len(choices) == 21
    assert "BypassGovernanceRetention" not in choices
    assert choices["ListAllMyBuckets"] == "ListAllMyBuckets"
    for late in (
        "GetObjectAcl",
        "PutObjectAcl",
        "GetBucketAcl",
        "PutBucketAcl",
        "PutBucketVersioning",
        "CreateBucket",
        "DeleteBucket",
    ):
        assert choices[late] == late


@contextlib.contextmanager
def grantee(username):
    """A user, an access key for them, and the grant row that names them."""
    with user(
        {
            "username": username,
            "full_name": username,
            "group_create": True,
            "password": "test1234",
        }
    ) as u:
        key = call("s3.accesskey.create", {"name": f"{username} key", "username": username})
        try:
            yield (
                {"principal_type": "USER", "xid": u["uid"], "access": "READWRITE"},
                key,
            )
        finally:
            call("s3.accesskey.delete", key["id"])


def client(key):
    """A boto3 client against the server under test on port 9000. The
    checksum stance is stated rather than inherited from the installed
    botocore: CRC32, composed COMPOSITE over a multipart upload, which
    is what the daemon serves."""
    boto3 = pytest.importorskip("boto3")
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=f"http://{truenas_server.ip}:9000",
        aws_access_key_id=key["access_key"],
        aws_secret_access_key=key["secret"],
        region_name="us-east-1",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_supported",
            response_checksum_validation="when_supported",
        ),
    )


def random_file(size):
    """`size` bytes of noise in a temp file, and their md5."""
    digest = hashlib.md5()
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
        left = size
        while left:
            chunk = os.urandom(min(left, 1 << 20))
            f.write(chunk)
            digest.update(chunk)
            left -= len(chunk)
        return f.name, digest.hexdigest()


def md5_of(path):
    digest = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_boto3_roundtrip(owner):
    """The whole chain: a bucket with grants, access keys for the grantees,
    and clients that put and get objects through the daemon. Two grantees,
    because under `OBJECT_WRITER` every write is published under the
    requester's own uid, and the second one writing into a prefix the
    first created, and over the first's object, is what proves the `S3`
    permissions model ignores the modes those writes leave behind: the
    daemon makes the share root the owner's at 0755, nothing is opened on
    it, and neither grantee is fenced by it."""
    with (
        grantee("s3client") as (grant_a, key_a),
        grantee("s3client2") as (
            grant_b,
            key_b,
        ),
        bucket(grants=[grant_a, grant_b], object_ownership="OBJECT_WRITER"),
    ):
        assert call("service.control", "START", SERVICE, {"silent": False}, job=True)
        try:
            a, b = client(key_a), client(key_b)
            assert [x["Name"] for x in a.list_buckets()["Buckets"]] == ["test-bucket"]
            root = call("filesystem.stat", f"/mnt/{DATASET}/s3data")
            assert (root["uid"], root["mode"] & 0o777) == (owner["uid"], 0o755), "left as the daemon made it"

            a.put_object(Bucket="test-bucket", Key="pfx/hello.txt", Body=b"from a")
            assert a.get_object(Bucket="test-bucket", Key="pfx/hello.txt")["Body"].read() == b"from a"
            assert ssh(f"cat /mnt/{DATASET}/s3data/pfx/hello.txt") == "from a"
            # OBJECT_WRITER: the publish records the account that made it
            on_disk = call("filesystem.stat", f"/mnt/{DATASET}/s3data/pfx/hello.txt")
            assert on_disk["uid"] == grant_a["xid"]

            b.put_object(Bucket="test-bucket", Key="pfx/other.txt", Body=b"from b")
            b.put_object(Bucket="test-bucket", Key="pfx/hello.txt", Body=b"b over a")
            assert a.get_object(Bucket="test-bucket", Key="pfx/hello.txt")["Body"].read() == b"b over a"
            b.delete_object(Bucket="test-bucket", Key="pfx/hello.txt")
            assert [o["Key"] for o in a.list_objects_v2(Bucket="test-bucket")["Contents"]] == ["pfx/other.txt"]
        finally:
            call("service.control", "STOP", SERVICE, {"silent": False}, job=True)


def test_bucket_owner_enforced_writes_as_the_owner(owner):
    """Under `BUCKET_OWNER_ENFORCED` object ownership the grants are the
    whole of the access control: the same two grantees write into the
    share root the daemon made the owner's, and over each other, and
    everything they publish lands on disk as the owner's rather than the
    writer's. A key with no grant is still refused, since the value moves
    the uid the kernel sees and not who is authorized."""
    with (
        grantee("s3client") as (grant_a, key_a),
        grantee("s3client2") as (grant_b, key_b),
        grantee("s3stranger") as (_ungranted, key_c),
        bucket(grants=[grant_a, grant_b], object_ownership="BUCKET_OWNER_ENFORCED"),
        running_service(),
    ):
        call("etc.generate", "truenas_s3")
        row = parse(BUCKETS_CONF)['bucket "test-bucket"']
        assert (row["permissions_model"], row["object_ownership"]) == ("s3", "bucket_owner_enforced")

        a, b, stranger = client(key_a), client(key_b), client(key_c)
        a.put_object(Bucket="test-bucket", Key="pfx/hello.txt", Body=b"from a")
        b.put_object(Bucket="test-bucket", Key="pfx/hello.txt", Body=b"b over a")
        assert a.get_object(Bucket="test-bucket", Key="pfx/hello.txt")["Body"].read() == b"b over a"
        with pytest.raises(Exception, match="AccessDenied"):
            stranger.put_object(Bucket="test-bucket", Key="pfx/hello.txt", Body=b"from nobody")
        assert ssh(f"cat /mnt/{DATASET}/s3data/pfx/hello.txt") == "b over a"
        for path in ("s3data", "s3data/pfx", "s3data/pfx/hello.txt"):
            assert call("filesystem.stat", f"/mnt/{DATASET}/{path}")["uid"] == owner["uid"], path


def test_snapshot_version_rules(owner, versioning_licensed):
    """The selection needs a versioning state that lists versions, a
    pattern keeps to the daemon's grammar, and the pair renders only
    beside a selection."""
    for bad, field in (
        ({"snapshot_versions": ["s3-*"]}, "versioning"),
        ({"versioning": "ENABLED", "snapshot_versions": ["s3/*"]}, "snapshot_versions.0"),
        ({"versioning": "ENABLED", "snapshot_versions": ["a,b"]}, "snapshot_versions.0"),
        ({"versioning": "ENABLED", "snapshot_versions": [" s3-*"]}, "snapshot_versions.0"),
        ({"versioning": "ENABLED", "snapshot_versions": ["s3-*", "s3-*"]}, "snapshot_versions.1"),
        ({"versioning": "ENABLED", "snapshot_versions": ["*"], "snapshot_versions_max": 0}, "snapshot_versions_max"),
    ):
        with pytest.raises(ValidationErrors) as ve:
            call("sharing.s3.create", {"name": "frozen", "dataset": DATASET, "owner": OWNER, **bad})
        assert field in ve.value.errors[0].attribute, ve.value.errors

    with bucket(name="frozen", versioning="SUSPENDED", snapshot_versions=["daily-*", "manual keep"]) as b:
        assert b["snapshot_versions_max"] == 64
        call("etc.generate", "truenas_s3")
        row = parse(BUCKETS_CONF)['bucket "frozen"']
        assert row["versioning"] == "suspended"
        assert row["snapshot_versions"] == "daily-*, manual keep"
        assert row["snapshot_versions_max"] == "64"

        call("sharing.s3.update", b["id"], {"snapshot_versions": [], "snapshot_versions_max": 3})
        call("etc.generate", "truenas_s3")
        row = parse(BUCKETS_CONF)['bucket "frozen"']
        assert "snapshot_versions" not in row and "snapshot_versions_max" not in row


def test_force_disable_versioning_refuses_object_lock(owner, versioning_licensed):
    """A locked bucket keeps its version history for as long as it
    exists: the on-disk lock latch never clears, so a forced disable
    could only take the bucket out of service."""
    with bucket(name="locked", versioning="ENABLED", object_lock=True) as b:
        with pytest.raises(ValidationErrors) as ve:
            call("sharing.s3.force_disable_versioning", b["id"])
        assert "object lock" in ve.value.errors[0].errmsg

    # the latch outlives the config: a dataset root carrying it is a
    # locked bucket whatever the row says, and is refused the same way
    with bucket(name="latched") as b:
        ssh(f"setfattr -n trusted.tns3_latch -v 0x5453334200000001 /mnt/{DATASET}")
        with pytest.raises(ValidationErrors) as ve:
            call("sharing.s3.force_disable_versioning", b["id"])
        assert "object lock" in ve.value.errors[0].errmsg


def test_force_disable_versioning_clears_the_snapshot_selection(owner, versioning_licensed):
    """`snapshot_versions` cannot stand beside `versioning = off`, so the
    forced disable clears the selection in the same row write; the inert
    cap stays."""
    with bucket(name="frozen", versioning="SUSPENDED", snapshot_versions=["s3-*"]) as b:
        entry = call("sharing.s3.force_disable_versioning", b["id"])
        assert entry["versioning"] == "OFF"
        assert entry["snapshot_versions"] == []
        call("etc.generate", "truenas_s3")
        row = parse(BUCKETS_CONF)['bucket "frozen"']
        assert row["versioning"] == "off"
        assert "snapshot_versions" not in row


@pytest.mark.parametrize("role", ["SHARING_S3_WRITE", "SHARING_WRITE"])
def test_force_disable_versioning_roles(owner, role):
    """The endpoint carries the same write role as the CRUD methods, and
    a read-only holder is refused."""
    with bucket() as b:
        with unprivileged_user_client(roles=["SHARING_S3_READ"]) as c:
            with pytest.raises(CallError, match="Not authorized"):
                c.call("sharing.s3.force_disable_versioning", b["id"])
        with unprivileged_user_client(roles=[role]) as c:
            assert c.call("sharing.s3.force_disable_versioning", b["id"])["versioning"] == "OFF"


def test_force_disable_versioning_destroys_history(owner, versioning_licensed):
    """The whole workflow over the wire: an enabled bucket accumulates
    versions and a delete marker; the forced disable restarts the
    service, versioning reads never-enabled, minted ids stop resolving,
    and a deleted key stays deleted. The version files' physical removal
    is the daemon's background sweep and is not waited on here."""
    with (
        grantee("s3history") as (grant, key),
        bucket(versioning="ENABLED", grants=[grant]) as b,
        running_service(),
    ):
        s3 = client(key)
        s3.put_object(Bucket="test-bucket", Key="k1", Body=b"one")
        s3.put_object(Bucket="test-bucket", Key="k1", Body=b"two")
        s3.put_object(Bucket="test-bucket", Key="k2", Body=b"doomed")
        s3.delete_object(Bucket="test-bucket", Key="k2")

        assert s3.get_bucket_versioning(Bucket="test-bucket")["Status"] == "Enabled"
        listing = s3.list_object_versions(Bucket="test-bucket")
        assert len([v for v in listing["Versions"] if v["Key"] == "k1"]) == 2
        assert [m["Key"] for m in listing["DeleteMarkers"]] == ["k2"]
        superseded = next(
            v["VersionId"] for v in listing["Versions"] if v["Key"] == "k1" and not v["IsLatest"]
        )

        pid = service()["pids"]
        entry = call("sharing.s3.force_disable_versioning", b["id"])
        assert entry["versioning"] == "OFF"
        assert service()["pids"] != pid, "the forced disable is a restart"

        assert "Status" not in s3.get_bucket_versioning(Bucket="test-bucket")
        listing = s3.list_object_versions(Bucket="test-bucket")
        assert [(v["Key"], v["VersionId"]) for v in listing.get("Versions", [])] == [("k1", "null")]
        assert listing.get("DeleteMarkers", []) == []
        assert s3.get_object(Bucket="test-bucket", Key="k1")["Body"].read() == b"two"
        with pytest.raises(Exception, match="NoSuchVersion"):
            s3.get_object(Bucket="test-bucket", Key="k1", VersionId=superseded)
        with pytest.raises(Exception, match="NoSuchKey"):
            s3.get_object(Bucket="test-bucket", Key="k2")

        # already off: the second call is an idempotent no-op — the row
        # stands and the service reloads rather than restarts
        pid = service()["pids"]
        assert call("sharing.s3.force_disable_versioning", b["id"])["versioning"] == "OFF"
        assert service()["pids"] == pid


def snapshot_id(name):
    """The wire id of a snapshot-derived version: `zfs.` then the name in
    lowercase hex."""
    return "zfs." + name.encode().hex()


def test_snapshots_serve_as_versions(owner, versioning_licensed):
    """The dataset's own snapshots, selected by pattern, serve each key's
    frozen state as a read-only version: listed beside the live one and
    read by id. The snapshots are taken before the first listing, since
    the daemon caches a bucket's snapshot set once a listing reads it.
    Raising or lowering the listing cap is a registry change, so a
    restart, after which the listing consults only the newest N while a
    selected snapshot past the cap still reads by id."""
    with (
        grantee("s3history") as (_grant, key),
        bucket(owner="s3history", versioning="SUSPENDED", snapshot_versions=["s3-*"]),
    ):
        assert call("service.control", "START", SERVICE, {"silent": False}, job=True)
        made = []
        try:
            s3 = client(key)
            s3.put_object(Bucket="test-bucket", Key="k1", Body=b"alpha state")
            ssh(f"zfs snapshot {DATASET}@s3-alpha")
            made.append("s3-alpha")
            s3.put_object(Bucket="test-bucket", Key="k1", Body=b"beta state")
            ssh(f"zfs snapshot {DATASET}@s3-beta")
            made.append("s3-beta")
            ssh(f"zfs snapshot {DATASET}@manual-keep")
            made.append("manual-keep")
            s3.put_object(Bucket="test-bucket", Key="k1", Body=b"live state")

            alpha, beta, keep = snapshot_id("s3-alpha"), snapshot_id("s3-beta"), snapshot_id("manual-keep")
            assert s3.get_bucket_versioning(Bucket="test-bucket")["Status"] == "Suspended"
            versions = s3.list_object_versions(Bucket="test-bucket").get("Versions", [])
            ids = [v["VersionId"] for v in versions if v["Key"] == "k1"]
            assert "null" in ids and alpha in ids and beta in ids, ids
            assert keep not in ids, "an unselected snapshot serves nothing"
            assert s3.get_object(Bucket="test-bucket", Key="k1", VersionId=alpha)["Body"].read() == b"alpha state"
            assert s3.get_object(Bucket="test-bucket", Key="k1", VersionId=beta)["Body"].read() == b"beta state"
            assert s3.get_object(Bucket="test-bucket", Key="k1")["Body"].read() == b"live state"
            with pytest.raises(Exception, match="NoSuchVersion"):
                s3.get_object(Bucket="test-bucket", Key="k1", VersionId=keep)

            pid = service()["pids"]
            b = call("sharing.s3.query", [["name", "=", "test-bucket"]], {"get": True})
            call("sharing.s3.update", b["id"], {"snapshot_versions_max": 1})
            assert service()["pids"] != pid, "the listing cap is a restart"
            versions = s3.list_object_versions(Bucket="test-bucket").get("Versions", [])
            ids = [v["VersionId"] for v in versions if v["Key"] == "k1"]
            assert beta in ids and alpha not in ids, ids
            assert s3.get_object(Bucket="test-bucket", Key="k1", VersionId=alpha)["Body"].read() == b"alpha state"
        finally:
            call("service.control", "STOP", SERVICE, {"silent": False}, job=True)
            for name in made:
                # a snapshot a reader crossed into is mounted, and its unmount
                # can trail the reader by a moment
                ssh(f"for i in 1 2 3 4 5; do zfs destroy {DATASET}@{name} && break; sleep 1; done")


SOSAPI_SYSTEM = ".system-d26a9498-cb7c-4a87-a44a-8ae204f5ba6c/system.xml"


def test_the_sosapi_block_size_follows_the_recordsize(owner):
    """Nothing about the block size is stored: the daemon reads the
    dataset's recordsize when Veeam asks for system.xml, so tuning the
    dataset changes the recommendation at the next ask with no reload
    and no restart. ZFS's 128K default recommends nothing."""
    with grantee("s3veeam") as (_grant, key), bucket(owner="s3veeam"):
        assert call("service.control", "START", SERVICE, {"silent": False}, job=True)
        try:
            pid = service()["pids"]
            s3 = client(key)

            def system_xml():
                return s3.get_object(Bucket="test-bucket", Key=SOSAPI_SYSTEM)["Body"].read().decode()

            assert "SystemRecommendations" not in system_xml()
            ssh(f"zfs set recordsize=1M {DATASET}")
            assert "<SystemRecommendations><KbBlockSize>1024</KbBlockSize></SystemRecommendations>" in system_xml()
            ssh(f"zfs set recordsize=2M {DATASET}")
            assert "<KbBlockSize>4096</KbBlockSize>" in system_xml()
            ssh(f"zfs inherit recordsize {DATASET}")
            assert "SystemRecommendations" not in system_xml()
            assert service()["pids"] == pid
        finally:
            call("service.control", "STOP", SERVICE, {"silent": False}, job=True)


@pytest.mark.parametrize(
    "size,threshold,parts,multipart_etag",
    [
        # one PUT: the transfer manager only splits above its threshold
        (5 << 20, 8 << 20, 1, "COMPOSITE"),
        # three parts: the multipart path, staged in the side tree the
        # daemon owns and published into s3data/ under the requester
        (12 << 20, 5 << 20, 3, "COMPOSITE"),
        # the same three parts on a row that declines to hash them: the
        # transfer manager declares CRC32 and sends no Content-MD5, so
        # nothing gives the daemon a reason to, and the object is minted
        (12 << 20, 5 << 20, 3, "MINTED"),
    ],
    ids=["single_put", "multipart", "minted_multipart"],
)
def test_a_file_survives_the_round_trip(owner, size, threshold, parts, multipart_etag):
    """A real file up and back down through the transfer manager, byte
    for byte, landing in s3data/ as the uploader's own file while the side
    tree beside it stays the daemon's. The bucket middleware provisioned
    has to carry both, which no tiny put_object proves."""
    from boto3.s3.transfer import TransferConfig

    transfer = TransferConfig(multipart_threshold=threshold, multipart_chunksize=5 << 20)
    source, expected = random_file(size)
    fetched = source + ".down"
    try:
        with (
            grantee("s3client") as (_grant, key),
            bucket(owner="s3client", multipart_etag=multipart_etag, object_ownership="OBJECT_WRITER"),
        ):
            assert call("service.control", "START", SERVICE, {"silent": False}, job=True)
            try:
                s3 = client(key)
                s3.upload_file(
                    source,
                    "test-bucket",
                    "big/file.bin",
                    ExtraArgs={"ChecksumAlgorithm": "CRC32"},
                    Config=transfer,
                )
                head = s3.head_object(Bucket="test-bucket", Key="big/file.bin")
                assert head["ContentLength"] == size
                # the ETag says which path the bytes took: a composite is
                # the md5 of the part md5s with the part count appended; a
                # single put, or a multipart the row declined to hash, is
                # a minted UUID
                etag = head["ETag"].strip('"')
                if parts > 1 and multipart_etag == "COMPOSITE":
                    assert re.fullmatch(rf"[0-9a-f]{{32}}-{parts}", etag), etag
                else:
                    assert re.fullmatch(r"[0-9a-f-]{36}", etag), etag

                s3.download_file("test-bucket", "big/file.bin", fetched, Config=transfer)
                assert md5_of(fetched) == expected

                on_disk = f"/mnt/{DATASET}/s3data/big/file.bin"
                assert ssh(f"md5sum {on_disk}").split()[0] == expected
                uid = call("user.query", [["username", "=", "s3client"]], {"get": True})["uid"]
                assert call("filesystem.stat", on_disk)["uid"] == uid
                assert call("filesystem.stat", f"/mnt/{DATASET}/.truenas_s3")["uid"] == 0
            finally:
                call("service.control", "STOP", SERVICE, {"silent": False}, job=True)
    finally:
        for path in (source, fetched):
            with contextlib.suppress(FileNotFoundError):
                os.unlink(path)
