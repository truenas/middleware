# TODO: re-enable once the truenas_s3 daemon is added to the TrueNAS image.
# Every test here starts the service and talks to the daemon.
"""S3 buckets: a dataset this plugin creates and registers with the S3
service, with its access grants embedded. Registering, dropping,
enabling or disabling a bucket restarts the service; its owner, grants
and audit mask reload."""

import contextlib
import hashlib
import os
import re
import tempfile
from configparser import RawConfigParser

import pytest
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.pool import dataset, pool
from middlewared.test.integration.utils import call, ssh

# TRUENAS_S3_DAEMON=1 runs them on a box that has the daemon installed by hand.
pytestmark = pytest.mark.skipif(
    not os.environ.get("TRUENAS_S3_DAEMON"),
    reason="the truenas_s3 daemon is not in the TrueNAS image yet",
)

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


@contextlib.contextmanager
def running_service():
    assert call("service.control", "START", SERVICE, {"silent": False}, job=True)
    try:
        yield
    finally:
        call("service.control", "STOP", SERVICE, {"silent": False}, job=True)


# the ACL a deployment puts on the share root when more than the owner is
# to write into it, as it would for any share: every write is published
# under the requesting account, and the daemon leaves the directory it
# created at 0755 owned by the owner
OPEN_ACL = [
    {"tag": "owner@", "type": "ALLOW", "perms": {"BASIC": "FULL_CONTROL"}, "flags": {"BASIC": "INHERIT"}},
    {"tag": "group@", "type": "ALLOW", "perms": {"BASIC": "FULL_CONTROL"}, "flags": {"BASIC": "INHERIT"}},
    {"tag": "everyone@", "type": "ALLOW", "perms": {"BASIC": "MODIFY"}, "flags": {"BASIC": "INHERIT"}},
]


def open_share_root(uid, gid):
    call("filesystem.setacl", {"path": f"/mnt/{DATASET}/s3data", "dacl": OPEN_ACL, "uid": uid, "gid": gid}, job=True)


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
    daemon's to make: absent until the service starts, then the owner's."""
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
            assert (data["uid"], data["gid"]) == (owner["uid"], owner["group"]["bsdgrp_gid"])
            assert data["mode"] & 0o777 == 0o755

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


def test_existing_dataset_is_refused(owner):
    with dataset("s3-preexisting") as ds:
        with pytest.raises(ValidationErrors):
            call("sharing.s3.create", {"name": "adopt-me", "dataset": ds, "owner": OWNER})
        assert not call("sharing.s3.query", [["name", "=", "adopt-me"]])


@pytest.mark.parametrize("name", ["UPPER", "ab", "a..b", "192.168.1.1", "-lead", "trail-"])
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
    # each, so the one field spells every rule it could
    with bucket(
        name="locked",
        versioning="ENABLED",
        object_lock=True,
        object_lock_default_mode="COMPLIANCE",
        object_lock_default_days=365,
    ):
        call("etc.generate", "truenas_s3")
        row = parse(BUCKETS_CONF)['bucket "locked"']
        assert row["versioning"] == "enabled"
        assert row["object_lock"] == "enabled"
        assert row["object_lock_default_mode"] == "compliance"
        assert row["object_lock_default_days"] == "365"
        assert "object_lock_default_years" not in row


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
    entry = call("sharing.s3.create", {"name": "doomed", "dataset": DATASET, "owner": OWNER})
    assert call("pool.dataset.attachments", entry["dataset"]) == [
        {"type": "S3 Bucket", "service": SERVICE, "attachments": ["doomed"]}
    ]
    call("pool.dataset.delete", entry["dataset"])
    assert not call("sharing.s3.query", [["id", "=", entry["id"]]])
    assert zfs_props(DATASET, ["mountpoint"]) is None


def test_owner_change_moves_the_grants_not_the_directory(owner):
    """A new owner takes the bypass and the render, and nothing on disk:
    the share root is the deployment's once the daemon has made it, and
    the daemon leaves it as found on every later start."""
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
        assert (data["uid"], data["gid"]) == (owner["uid"], owner["group"]["bsdgrp_gid"])
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
        key = call("s3.accesskey.create", {"name": f"{username} key", "username": username})
        try:
            yield (
                {"principal_type": "USER", "xid": u["uid"], "access": "READWRITE"},
                key,
            )
        finally:
            call("s3.accesskey.delete", key["id"])


def client(key):
    """A boto3 client on the daemon. The checksum stance is stated rather
    than inherited from the installed botocore: CRC32, composed COMPOSITE
    over a multipart upload, which is what the daemon serves."""
    boto3 = pytest.importorskip("boto3")
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url="http://127.0.0.1:9000",
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
    because every write is published under the requester's own uid: the
    second one writing into a prefix the first created, and over the
    first's object, is what an inheritable ACL on the share root is for,
    and without one the second grantee is refused at the root: the daemon
    makes the directory the owner's and every write is the requester's."""
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
            with pytest.raises(Exception, match="AccessDenied"):
                a.put_object(Bucket="test-bucket", Key="pfx/hello.txt", Body=b"from a")
            open_share_root(owner["uid"], owner["group"]["bsdgrp_gid"])
            a.put_object(Bucket="test-bucket", Key="pfx/hello.txt", Body=b"from a")
            assert a.get_object(Bucket="test-bucket", Key="pfx/hello.txt")["Body"].read() == b"from a"
            assert ssh(f"cat /mnt/{DATASET}/s3data/pfx/hello.txt") == "from a"

            b.put_object(Bucket="test-bucket", Key="pfx/other.txt", Body=b"from b")
            b.put_object(Bucket="test-bucket", Key="pfx/hello.txt", Body=b"b over a")
            assert a.get_object(Bucket="test-bucket", Key="pfx/hello.txt")["Body"].read() == b"b over a"
            b.delete_object(Bucket="test-bucket", Key="pfx/hello.txt")
            assert [o["Key"] for o in a.list_objects_v2(Bucket="test-bucket")["Contents"]] == ["pfx/other.txt"]
        finally:
            call("service.control", "STOP", SERVICE, {"silent": False}, job=True)


def test_snapshot_version_rules(owner):
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


def snapshot_id(name):
    """The wire id of a snapshot-derived version: `zfs.` then the name in
    lowercase hex."""
    return "zfs." + name.encode().hex()


def test_snapshots_serve_as_versions(owner):
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
    "size,threshold,parts",
    [
        # one PUT: the transfer manager only splits above its threshold
        (5 << 20, 8 << 20, 1),
        # three parts: the multipart path, staged in the side tree the
        # daemon owns and published into s3data/ under the requester
        (12 << 20, 5 << 20, 3),
    ],
    ids=["single_put", "multipart"],
)
def test_a_file_survives_the_round_trip(owner, size, threshold, parts):
    """A real file up and back down through the transfer manager, byte
    for byte, landing in s3data/ as the uploader's own file while the side
    tree beside it stays the daemon's. The bucket middleware provisioned
    has to carry both, which no tiny put_object proves."""
    from boto3.s3.transfer import TransferConfig

    transfer = TransferConfig(multipart_threshold=threshold, multipart_chunksize=5 << 20)
    source, expected = random_file(size)
    fetched = source + ".down"
    try:
        with grantee("s3client") as (_grant, key), bucket(owner="s3client"):
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
                # the md5 of the part md5s with the part count appended, a
                # single put a minted UUID
                etag = head["ETag"].strip('"')
                if parts > 1:
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
