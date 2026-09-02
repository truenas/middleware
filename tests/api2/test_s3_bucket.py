"""S3 buckets: a dataset this plugin creates and registers with the S3
service, with its access grants embedded. Registering, dropping,
enabling or disabling a bucket restarts the service; its owner, grants
and audit mask reload."""

import contextlib
from configparser import RawConfigParser

import pytest
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.pool import dataset, pool
from middlewared.test.integration.utils import call, ssh

SERVICE = "truenas_s3"
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
    requires, its data directory belongs to the owner under an ACL every
    grantee satisfies, and the bucket captures its mount point and the
    owner's uid."""
    with bucket() as b:
        assert b["path"] == f"/mnt/{DATASET}"
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

        root = call("filesystem.stat", b["path"])
        assert (root["uid"], root["gid"]) == (0, 0), "the side tree stays root's"
        data = call("filesystem.getacl", f"{b['path']}/data")
        assert data["uid"] == owner["uid"]
        assert data["gid"] == owner["group"]["bsdgrp_gid"]
        assert data["acltype"] == "NFS4"
        everyone = [ace for ace in data["acl"] if ace["tag"] == "everyone@"]
        assert everyone[0]["perms"] == {"BASIC": "MODIFY"}
        assert everyone[0]["flags"] == {"BASIC": "INHERIT"}

        call("etc.generate", "truenas_s3")
        row = parse(BUCKETS_CONF)['bucket "test-bucket"']
        assert row == {
            "dataset": DATASET,
            "path": f"/mnt/{DATASET}",
            "owner": OWNER,
            "owner_id": str(owner["uid"]),
            "permissions_model": "s3",
            "versioning": "off",
            "object_lock": "off",
        }

    assert zfs_props(DATASET, ["mountpoint"]) is None


def test_delete_keeps_the_dataset(owner):
    entry = call(
        "sharing.s3.create", {"name": "keeps-data", "dataset": DATASET, "owner": OWNER}
    )
    try:
        ssh(f"touch /mnt/{DATASET}/marker")
        call("sharing.s3.delete", entry["id"])
        assert not call("sharing.s3.query", [["id", "=", entry["id"]]])
        assert zfs_props(DATASET, ["mounted"]) == {"mounted": "yes"}
        assert ssh(f"ls /mnt/{DATASET}").split() == ["data", "marker"]
        call("etc.generate", "truenas_s3")
        assert 'bucket "keeps-data"' not in parse(BUCKETS_CONF)
    finally:
        call("zfs.resource.destroy", {"path": DATASET, "recursive": True})


def test_existing_dataset_is_refused(owner):
    with dataset("s3-preexisting") as ds:
        with pytest.raises(ValidationErrors):
            call(
                "sharing.s3.create", {"name": "adopt-me", "dataset": ds, "owner": OWNER}
            )
        assert not call("sharing.s3.query", [["name", "=", "adopt-me"]])


@pytest.mark.parametrize(
    "name", ["UPPER", "ab", "a..b", "192.168.1.1", "-lead", "trail-"]
)
def test_bad_names_are_refused(owner, name):
    with pytest.raises(ValidationErrors):
        call("sharing.s3.create", {"name": name, "dataset": DATASET, "owner": OWNER})


def test_unknown_owner_is_refused():
    with pytest.raises(ValidationErrors) as ve:
        call(
            "sharing.s3.create",
            {"name": "no-owner", "dataset": DATASET, "owner": "nosuchuser"},
        )
    assert "does not exist" in ve.value.errors[0].errmsg
    assert zfs_props(DATASET, ["mountpoint"]) is None, "nothing was created"


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
        assert parse(POLICIES_CONF) == {
            'grant everyone "test-bucket"': {"access": "deny"}
        }

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


def test_object_lock_rules(owner):
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
                "object_lock_default_mode": "COMPLIANCE",
                "object_lock_default_days": 30,
                "object_lock_default_years": 1,
            },
            "object_lock_default_years",
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

    with bucket(
        name="locked",
        versioning="ENABLED",
        object_lock=True,
        object_lock_default_mode="COMPLIANCE",
        object_lock_default_years=1,
        sosapi_block_size=1024,
    ):
        call("etc.generate", "truenas_s3")
        row = parse(BUCKETS_CONF)['bucket "locked"']
        assert row["versioning"] == "enabled"
        assert row["object_lock"] == "enabled"
        assert row["object_lock_default_mode"] == "compliance"
        assert row["object_lock_default_years"] == "1"
        assert "object_lock_default_days" not in row
        assert row["sosapi_block_size"] == "1024"


def test_registry_changes_restart_and_the_rest_reload(owner):
    assert call("service.control", "START", SERVICE, {"silent": False}, job=True)
    try:
        pid = service()["pids"]
        with bucket() as b:
            after_create = service()["pids"]
            assert after_create != pid, "registering a bucket is a restart"

            call(
                "sharing.s3.update",
                b["id"],
                {"grants": [{"principal_type": "EVERYONE", "access": "READONLY"}]},
            )
            assert service()["pids"] == after_create, "a grant change is a reload"

            call("sharing.s3.update", b["id"], {"enabled": False})
            after_disable = service()["pids"]
            assert after_disable != after_create, "disabling a bucket is a restart"
            assert 'bucket "test-bucket"' not in parse(BUCKETS_CONF)

            call("sharing.s3.update", b["id"], {"enabled": True})
            assert 'bucket "test-bucket"' in parse(BUCKETS_CONF)
        assert service()["state"] == "RUNNING"
    finally:
        call("service.control", "STOP", SERVICE, {"silent": False}, job=True)


def test_destroying_the_dataset_deregisters_the_bucket(owner):
    entry = call(
        "sharing.s3.create", {"name": "doomed", "dataset": DATASET, "owner": OWNER}
    )
    assert call("pool.dataset.attachments", entry["dataset"]) == [
        {"type": "S3 Bucket", "service": SERVICE, "attachments": ["doomed"]}
    ]
    call("pool.dataset.delete", entry["dataset"])
    assert not call("sharing.s3.query", [["id", "=", entry["id"]]])
    assert zfs_props(DATASET, ["mountpoint"]) is None


def test_owner_change_hands_over_the_data_directory(owner):
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
    ):
        ssh(f"touch /mnt/{DATASET}/data/theirs")
        updated = call("sharing.s3.update", b["id"], {"owner": "s3newowner"})
        assert updated["owner_uid"] == new["uid"]
        data = call("filesystem.stat", f"{b['path']}/data")
        assert (data["uid"], data["gid"]) == (new["uid"], new["group"]["bsdgrp_gid"])
        # not recursive: what the old owner wrote stays theirs
        assert call("filesystem.stat", f"{b['path']}/data/theirs")["uid"] == 0
        call("etc.generate", "truenas_s3")
        row = parse(BUCKETS_CONF)['bucket "test-bucket"']
        assert (row["owner"], row["owner_id"]) == ("s3newowner", str(new["uid"]))


def test_audit_choices():
    choices = call("sharing.s3.audit_choices")
    assert len(choices) == 14
    assert "BypassGovernanceRetention" not in choices
    assert choices["ListAllMyBuckets"] == "ListAllMyBuckets"


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
        key = call(
            "s3.accesskey.create", {"name": f"{username} key", "username": username}
        )
        try:
            yield (
                {"principal_type": "USER", "xid": u["uid"], "access": "READWRITE"},
                key,
            )
        finally:
            call("s3.accesskey.delete", key["id"])


def test_boto3_roundtrip(owner):
    """The whole chain: a bucket with grants, access keys for the grantees,
    and clients that put and get objects through the daemon. Two grantees,
    because every write is published under the requester's own uid: the
    second one writing into a prefix the first created, and over the
    first's object, is what the data directory's inherited ACL is for."""
    boto3 = pytest.importorskip("boto3")
    from botocore.config import Config

    def client(key):
        return boto3.client(
            "s3",
            endpoint_url="http://127.0.0.1:9000",
            aws_access_key_id=key["access_key"],
            aws_secret_access_key=key["secret"],
            region_name="us-east-1",
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    with (
        grantee("s3client") as (grant_a, key_a),
        grantee("s3client2") as (
            grant_b,
            key_b,
        ),
        bucket(grants=[grant_a, grant_b]),
    ):
        assert call("service.control", "START", SERVICE, {"silent": False}, job=True)
        try:
            a, b = client(key_a), client(key_b)
            assert [x["Name"] for x in a.list_buckets()["Buckets"]] == ["test-bucket"]
            a.put_object(Bucket="test-bucket", Key="pfx/hello.txt", Body=b"from a")
            assert (
                a.get_object(Bucket="test-bucket", Key="pfx/hello.txt")["Body"].read()
                == b"from a"
            )
            assert ssh(f"cat /mnt/{DATASET}/data/pfx/hello.txt") == "from a"

            b.put_object(Bucket="test-bucket", Key="pfx/other.txt", Body=b"from b")
            b.put_object(Bucket="test-bucket", Key="pfx/hello.txt", Body=b"b over a")
            assert (
                a.get_object(Bucket="test-bucket", Key="pfx/hello.txt")["Body"].read()
                == b"b over a"
            )
            b.delete_object(Bucket="test-bucket", Key="pfx/hello.txt")
            assert [
                o["Key"] for o in a.list_objects_v2(Bucket="test-bucket")["Contents"]
            ] == ["pfx/other.txt"]
        finally:
            call("service.control", "STOP", SERVICE, {"silent": False}, job=True)
