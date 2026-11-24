"""The bucket plane: bucket operations middleware owns, driven over S3.

The daemon performs none of `CreateBucket`, `DeleteBucket`,
`PutBucketVersioning` and `PutObjectLockConfiguration` itself. It calls
`sharing.s3.*` as the account that made the request, so the access key
must carry `manage_buckets` and the account must hold
`SHARING_S3_WRITE`.
"""

import contextlib
import uuid

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call
import pytest
from s3_client import code_of, drain, status_of

#: A create over the wire goes under the service's managed root.
MANAGED_ROOT = "s3proto-managed"


def wire_name() -> str:
    """A bucket name no other run holds."""
    return f"s3proto-made-{uuid.uuid4().hex[:12]}"


def row_for(name: str):
    rows = call("sharing.s3.query", [["name", "=", name]])
    return rows[0] if rows else None


@pytest.fixture(scope="module")
def managed_root(s3_deployment):
    """A dataset for the service to derive bucket datasets under."""
    was = call("s3.config")["managed_root_dataset"]
    with dataset(MANAGED_ROOT) as root:
        call("s3.update", {"managed_root_dataset": root})
        try:
            yield root
        finally:
            call("s3.update", {"managed_root_dataset": was})


@pytest.fixture
def made(admin_s3, managed_root):
    """A bucket made over the wire, removed however the case ends: the
    row, then the dataset a deregistration deliberately keeps."""
    name = wire_name()
    admin_s3.create_bucket(Bucket=name)
    entry = row_for(name)
    assert entry is not None, f"{name} was created and middleware holds no row"
    try:
        yield name
    finally:
        with contextlib.suppress(Exception):
            drain(admin_s3, name)
        with contextlib.suppress(Exception):
            admin_s3.delete_bucket(Bucket=name)
        with contextlib.suppress(Exception):
            call("zfs.resource.destroy", {"path": entry["dataset"], "recursive": True})


# ── the create reaches middleware, and what it says when it does ─────


def test_a_flagged_key_creates_and_deletes(admin_s3, made):
    """The plane works at all: the bucket is listed, then it is not."""
    assert made in {b["Name"] for b in admin_s3.list_buckets().get("Buckets", [])}
    admin_s3.delete_bucket(Bucket=made)
    assert made not in {b["Name"] for b in admin_s3.list_buckets().get("Buckets", [])}
    assert row_for(made) is None, "the wire delete took the registry row with it"


def test_the_row_the_create_left_is_the_payload_the_daemon_sent(accounts, made, managed_root):
    """The row a create leaves: owned by the caller, no grants, enforced
    ownership, placed under the managed root."""
    entry = row_for(made)
    assert entry["owner"] == accounts["main"].username
    assert entry["owner_uid"] == accounts["main"].uid
    assert entry["grants"] == []
    assert entry["object_ownership"] == "BUCKET_OWNER_ENFORCED"
    assert entry["permissions_model"] == "S3"
    assert entry["versioning"] == "OFF"
    assert entry["object_lock"] is False
    assert entry["enabled"] is True
    assert entry["dataset"] == f"{managed_root}/{made}"


def test_the_creator_owns_what_it_made(admin_s3, made):
    """The owner bypasses the grants, so a bucket with no rows is usable."""
    admin_s3.put_object(Bucket=made, Key="mine.bin", Body=b"mine")
    assert admin_s3.get_object(Bucket=made, Key="mine.bin")["Body"].read() == b"mine"


def test_a_second_create_of_your_own_bucket_says_so(admin_s3, made):
    """`BucketAlreadyOwnedByYou`, not `BucketAlreadyExists`."""
    with pytest.raises(Exception) as caught:
        admin_s3.create_bucket(Bucket=made)
    assert code_of(caught.value) == "BucketAlreadyOwnedByYou"


def test_a_recreated_name_does_not_land_on_the_old_data(admin_s3, managed_root):
    """`sharing.s3.delete` keeps the dataset, so a second bucket of the
    same name gets a new one, suffixed `_N`."""
    name = wire_name()
    datasets = []
    try:
        admin_s3.create_bucket(Bucket=name)
        first = row_for(name)["dataset"]
        datasets.append(first)
        assert first == f"{managed_root}/{name}"

        admin_s3.delete_bucket(Bucket=name)
        assert row_for(name) is None
        assert call("zfs.resource.list", {"paths": [first], "properties": None}), "the dataset is kept"

        admin_s3.create_bucket(Bucket=name)
        second = row_for(name)["dataset"]
        datasets.append(second)
        assert second == f"{managed_root}/{name}_1", second
    finally:
        with contextlib.suppress(Exception):
            admin_s3.delete_bucket(Bucket=name)
        for path in datasets:
            with contextlib.suppress(Exception):
                call("zfs.resource.destroy", {"path": path, "recursive": True})


def test_a_delete_of_a_populated_bucket_is_refused(admin_s3, made):
    """`BucketNotEmpty` is the daemon's check: `sharing.s3.delete` itself
    would deregister the bucket and keep its objects."""
    admin_s3.put_object(Bucket=made, Key="occupied.bin", Body=b"x")
    with pytest.raises(Exception) as caught:
        admin_s3.delete_bucket(Bucket=made)
    assert code_of(caught.value) == "BucketNotEmpty"
    assert row_for(made) is not None, "the refused delete left the row standing"

    admin_s3.delete_object(Bucket=made, Key="occupied.bin")
    admin_s3.delete_bucket(Bucket=made)
    assert row_for(made) is None


def test_a_delete_of_a_name_nobody_holds_is_no_such_bucket(admin_s3):
    with pytest.raises(Exception) as caught:
        admin_s3.delete_bucket(Bucket=wire_name())
    assert code_of(caught.value) == "NoSuchBucket"


# ── what the create may ask for ──────────────────────────────────────


def test_a_create_naming_an_acl_on_an_enforced_bucket_is_refused(admin_s3, managed_root):
    """The default ownership has no ACL surface, so an ACL named beside
    it is refused before the bucket is made."""
    name = wire_name()
    with pytest.raises(Exception) as caught:
        admin_s3.create_bucket(Bucket=name, ACL="public-read")
    assert code_of(caught.value) == "AccessControlListNotSupported"
    assert row_for(name) is None, "a refused create made nothing"


def test_a_create_may_ask_for_an_acl_surface_and_get_one(admin_s3, managed_root):
    """`x-amz-object-ownership` reaches the registry, and the ACL headers
    reach the bucket's own record, not the registry's `grants` array."""
    name = wire_name()
    try:
        admin_s3.create_bucket(Bucket=name, ObjectOwnership="ObjectWriter", ACL="public-read")
        entry = row_for(name)
        assert entry["object_ownership"] == "OBJECT_WRITER"
        assert entry["grants"] == [], "an ACL is not a registry grant"

        acl = admin_s3.get_bucket_acl(Bucket=name)
        assert any(
            g["Permission"] == "READ" and g["Grantee"].get("URI", "").endswith("AllUsers") for g in acl["Grants"]
        ), acl["Grants"]
    finally:
        with contextlib.suppress(Exception):
            admin_s3.delete_bucket(Bucket=name)
        if (entry := row_for(name)) is not None:
            with contextlib.suppress(Exception):
                call("zfs.resource.destroy", {"path": entry["dataset"], "recursive": True})


def test_an_ownership_spelling_s3_does_not_define_is_refused(admin_s3, managed_root):
    name = wire_name()
    with pytest.raises(Exception) as caught:
        admin_s3.create_bucket(Bucket=name, ObjectOwnership="BucketOwnerWhatever")
    assert status_of(caught.value) == 400
    assert row_for(name) is None


def test_object_lock_is_expressible_only_at_creation(admin_s3, managed_root):
    """A create with object lock carries `versioning: ENABLED` with it."""
    name = wire_name()
    entry = None
    try:
        admin_s3.create_bucket(Bucket=name, ObjectLockEnabledForBucket=True)
        entry = row_for(name)
        assert entry["object_lock"] is True
        assert entry["versioning"] == "ENABLED", "a locked row is a versioned row"

        got = admin_s3.get_object_lock_configuration(Bucket=name)
        assert got["ObjectLockConfiguration"]["ObjectLockEnabled"] == "Enabled"
    finally:
        with contextlib.suppress(Exception):
            drain(admin_s3, name)
        with contextlib.suppress(Exception):
            admin_s3.delete_bucket(Bucket=name)
        if entry is not None:
            with contextlib.suppress(Exception):
                call("zfs.resource.destroy", {"path": entry["dataset"], "recursive": True})


def test_a_create_with_no_managed_root_is_refused(admin_s3, managed_root):
    """An S3 client sends only a bucket name, so with no
    `managed_root_dataset` there is nowhere to put the dataset."""
    call("s3.update", {"managed_root_dataset": ""})
    try:
        name = wire_name()
        with pytest.raises(Exception):
            admin_s3.create_bucket(Bucket=name)
        assert row_for(name) is None
    finally:
        call("s3.update", {"managed_root_dataset": managed_root})


# ── the key's own ceiling ────────────────────────────────────────────


def test_an_unflagged_key_is_refused_on_all_four(s3, admin_s3, made):
    """The key's ceiling covers all four operations, whatever the grants."""
    for call_ in (
        lambda c: c.create_bucket(Bucket=wire_name()),
        lambda c: c.delete_bucket(Bucket=made),
        lambda c: c.put_bucket_versioning(Bucket=made, VersioningConfiguration={"Status": "Enabled"}),
        lambda c: c.put_object_lock_configuration(
            Bucket=made, ObjectLockConfiguration={"ObjectLockEnabled": "Enabled"}
        ),
    ):
        with pytest.raises(Exception) as caught:
            call_(s3)
        assert status_of(caught.value) == 403, "the key decides, not the grants"


def test_put_bucket_versioning_moves_the_registry_row(admin_s3, made):
    """The state a client sets is the row middleware stores, and the
    `200` is withheld until the reload has reached the daemon."""
    admin_s3.put_bucket_versioning(Bucket=made, VersioningConfiguration={"Status": "Enabled"})
    assert row_for(made)["versioning"] == "ENABLED"
    assert admin_s3.get_bucket_versioning(Bucket=made)["Status"] == "Enabled"

    # Fails if the answer outran the reload.
    assert admin_s3.put_object(Bucket=made, Key="versioned.bin", Body=b"v").get("VersionId")

    admin_s3.put_bucket_versioning(Bucket=made, VersioningConfiguration={"Status": "Suspended"})
    assert row_for(made)["versioning"] == "SUSPENDED"
    assert admin_s3.get_bucket_versioning(Bucket=made)["Status"] == "Suspended"


def test_there_is_no_wire_spelling_for_never_versioned(admin_s3, made):
    """S3 spells only `Enabled` and `Suspended`."""
    admin_s3.put_bucket_versioning(Bucket=made, VersioningConfiguration={"Status": "Enabled"})
    with pytest.raises(Exception):
        admin_s3.put_bucket_versioning(Bucket=made, VersioningConfiguration={"Status": "Off"})
    assert row_for(made)["versioning"] == "ENABLED"


def test_a_default_retention_rule_needs_a_bucket_that_can_hold_one(admin_s3, made):
    """Refused on a bucket whose lock was never enabled."""
    with pytest.raises(Exception) as caught:
        admin_s3.put_object_lock_configuration(
            Bucket=made,
            ObjectLockConfiguration={
                "ObjectLockEnabled": "Enabled",
                "Rule": {"DefaultRetention": {"Mode": "GOVERNANCE", "Days": 1}},
            },
        )
    assert status_of(caught.value) in (400, 409), status_of(caught.value)
    assert row_for(made)["object_lock_default_mode"] is None


def test_a_retention_period_past_the_ceiling_is_refused(admin_s3, managed_root):
    """A longer rule is one the S3 service would refuse its whole config over."""
    name = wire_name()
    entry = None
    try:
        admin_s3.create_bucket(Bucket=name, ObjectLockEnabledForBucket=True)
        entry = row_for(name)
        with pytest.raises(Exception) as caught:
            admin_s3.put_object_lock_configuration(
                Bucket=name,
                ObjectLockConfiguration={
                    "ObjectLockEnabled": "Enabled",
                    "Rule": {"DefaultRetention": {"Mode": "GOVERNANCE", "Days": 36501}},
                },
            )
        assert status_of(caught.value) in (400, 409)
        assert row_for(name)["object_lock_default_days"] is None

        # One day inside the ceiling is taken.
        admin_s3.put_object_lock_configuration(
            Bucket=name,
            ObjectLockConfiguration={
                "ObjectLockEnabled": "Enabled",
                "Rule": {"DefaultRetention": {"Mode": "GOVERNANCE", "Days": 36500}},
            },
        )
        stored = row_for(name)
        assert (stored["object_lock_default_mode"], stored["object_lock_default_days"]) == ("GOVERNANCE", 36500)
    finally:
        with contextlib.suppress(Exception):
            drain(admin_s3, name)
        with contextlib.suppress(Exception):
            admin_s3.delete_bucket(Bucket=name)
        if entry is not None:
            with contextlib.suppress(Exception):
                call("zfs.resource.destroy", {"path": entry["dataset"], "recursive": True})
