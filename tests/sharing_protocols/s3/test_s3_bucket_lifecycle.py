"""The bucket plane: the four operations middleware owns, driven over S3.

A bucket is a ZFS dataset and a registry row, both of which middleware
owns, so `CreateBucket`, `DeleteBucket`, `PutBucketVersioning` and
`PutObjectLockConfiguration` are not performed by the daemon. It calls
`sharing.s3.create`, `sharing.s3.delete` and `sharing.s3.update` over
its connector **as the account that made the request**, which is why the
account's own RBAC decides exactly as it would through the API.

This is the module the whole suite exists for. Every other file here
proves the daemon's answer; this one proves the wire and the API are the
same system — that a `CreateBucket` a client sent leaves a row
`sharing.s3.query` can read, with the fields the daemon said it sent,
and a dataset where middleware decided to put it.

**Two gates stand in front of it, and they are different gates.** The
access key must carry `manage_buckets`, which is checked before any
connector is reached; and the *account* must hold `SHARING_S3_WRITE`,
which is middleware's own check on the session the connector opened. The
session's `s3` client fails the first and `admin_s3` passes both, and
they are the same account on two keys that differ in nothing else — so a
refusal is attributable to the flag alone.
"""

import contextlib
import uuid

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call
import pytest
from s3_client import code_of, drain, status_of

#: A create with no `dataset` goes under the service's managed root, and
#: an S3 client can send nothing else — it has only a bucket name. With
#: no root configured the create is refused, which is its own case below.
MANAGED_ROOT = "s3proto-managed"


def wire_name() -> str:
    """A bucket name no other run holds."""
    return f"s3proto-made-{uuid.uuid4().hex[:12]}"


def row_for(name: str):
    rows = call("sharing.s3.query", [["name", "=", name]])
    return rows[0] if rows else None


@pytest.fixture(scope="module")
def managed_root(s3_deployment):
    """A dataset for the service to derive bucket datasets under.

    Restored on the way out: the setting is the S3 service's own and a
    suite that left it pointing at a dataset it had destroyed would
    refuse every later create for a reason nothing here explains.
    """
    was = call("s3.config")["managed_root_dataset"]
    with dataset(MANAGED_ROOT) as root:
        call("s3.update", {"managed_root_dataset": root})
        try:
            yield root
        finally:
            call("s3.update", {"managed_root_dataset": was})


@pytest.fixture
def made(admin_s3, managed_root):
    """A bucket this module made over the wire, removed however it ends.

    Both halves: the registry row through the wire's own `DeleteBucket`
    where it still stands, and the dataset by hand — deregistering a
    bucket deliberately keeps its objects, so nothing else would.
    """
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
    """The wiring assertion, stated as the row rather than as an answer.

    A created bucket admits its creator and nobody else: owned by the
    calling account, no grant rows, `BUCKET_OWNER_ENFORCED` under the
    `S3` permissions model. All three are middleware's own defaults and
    the daemon sends all three regardless, because a default that
    widened later would widen every bucket made this way with it — so
    reading them back is what says the payload arrived whole.

    The dataset is middleware's to place: under the service's managed
    root, taking the name of the bucket.
    """
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
    """A bucket with no grant rows is not an unusable bucket: its owner
    bypasses the grants, which is what makes the create self-sufficient.
    """
    admin_s3.put_object(Bucket=made, Key="mine.bin", Body=b"mine")
    assert admin_s3.get_object(Bucket=made, Key="mine.bin")["Body"].read() == b"mine"


def test_a_second_create_of_your_own_bucket_says_so(admin_s3, made):
    """`BucketAlreadyOwnedByYou`, not `BucketAlreadyExists`.

    The two are different facts and only one of them is actionable: a
    client that owns the name can carry on, and one that does not has to
    pick another. Telling them apart for a name nobody can read would
    answer "who owns this" to anyone who can guess one, which is why the
    distinction rests on the caller owning the row this server holds.
    """
    with pytest.raises(Exception) as caught:
        admin_s3.create_bucket(Bucket=made)
    assert code_of(caught.value) == "BucketAlreadyOwnedByYou"


def test_a_recreated_name_does_not_land_on_the_old_data(admin_s3, managed_root):
    """`sharing.s3.delete` keeps the dataset and its objects, so a second
    bucket of the same name must get a *new* dataset.

    If it did not, it would serve the objects of the first bucket — a
    client deleting a bucket and making it again would find someone
    else's data in it. Middleware adds a `_N` suffix; the separator is an
    underscore because a bucket name cannot contain one, so `backups_1`
    is unambiguously the second dataset for `backups`.
    """
    name = wire_name()
    datasets = []
    try:
        admin_s3.create_bucket(Bucket=name)
        first = row_for(name)["dataset"]
        datasets.append(first)
        assert first == f"{managed_root}/{name}"

        admin_s3.delete_bucket(Bucket=name)
        assert row_for(name) is None
        assert call("zfs.resource.query", [], {"extra": {"paths": [first], "properties": None}}), "the dataset is kept"

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
    """`BucketNotEmpty` — a check middleware does not make for itself.

    `sharing.s3.delete` deregisters a bucket and keeps its objects on
    purpose, so nothing on the API side refuses this. The daemon is what
    knows the tree is occupied, and answering the client is the only
    place it can be said.
    """
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
    """The default ownership is `BucketOwnerEnforced`, which has no ACL
    surface — so an ACL named beside it is refused before the bucket is
    made, rather than stored where nothing will read it."""
    name = wire_name()
    with pytest.raises(Exception) as caught:
        admin_s3.create_bucket(Bucket=name, ACL="public-read")
    assert code_of(caught.value) == "AccessControlListNotSupported"
    assert row_for(name) is None, "a refused create made nothing"


def test_a_create_may_ask_for_an_acl_surface_and_get_one(admin_s3, managed_root):
    """`x-amz-object-ownership` reaches the registry, and the ACL headers
    reach the bucket's own record — not the registry's `grants` array,
    which is the account-level share and which nothing on the wire
    addresses."""
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
    """The latch is written on the dataset root and never lowers, so a
    bucket made without object lock can never acquire it.

    The create carries `versioning: ENABLED` with it, which middleware
    requires of a locked row — so the row that comes back says both, and
    the registry and the latch agree by construction rather than by a
    later reconciliation.
    """
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
    """An S3 client sends only a bucket name, so the *service* decides
    where the dataset goes — and with no `managed_root_dataset` set there
    is nowhere to decide on.

    Refused rather than placed somewhere by default: a bucket is storage,
    and choosing a pool for one on a client's behalf is not a decision
    this service gets to make silently.
    """
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
    """**The ceiling covers four operations, not two.**

    Versioning and the default retention rule are registry fields on the
    same connector and both are irreversible in the direction that
    matters, so a key that may not make a bucket may not decide either.
    The refusal is the *key's*, not the grants': the same account's
    flagged key does all four, and the fixture above is the proof.
    """
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
    `200` is withheld until the reload has reached the daemon.

    That last part is what makes the assertion below safe to make at all:
    the field the engine re-reads per request is the old one until the
    reload lands, so a client that set versioning and immediately wrote
    would otherwise get the state it had just replaced.
    """
    admin_s3.put_bucket_versioning(Bucket=made, VersioningConfiguration={"Status": "Enabled"})
    assert row_for(made)["versioning"] == "ENABLED"
    assert admin_s3.get_bucket_versioning(Bucket=made)["Status"] == "Enabled"

    # A versioned write mints an id immediately, which is the half that
    # would fail if the answer had outrun the reload.
    assert admin_s3.put_object(Bucket=made, Key="versioned.bin", Body=b"v").get("VersionId")

    admin_s3.put_bucket_versioning(Bucket=made, VersioningConfiguration={"Status": "Suspended"})
    assert row_for(made)["versioning"] == "SUSPENDED"
    assert admin_s3.get_bucket_versioning(Bucket=made)["Status"] == "Suspended"


def test_there_is_no_wire_spelling_for_never_versioned(admin_s3, made):
    """S3 spells only `Enabled` and `Suspended`, so a bucket cannot be
    returned to never-versioned over the wire at all.

    `sharing.s3.force_disable_versioning` is the config plane's one path
    back, and it is a documented destruction of the history — which is
    exactly why it is not reachable from a client.
    """
    admin_s3.put_bucket_versioning(Bucket=made, VersioningConfiguration={"Status": "Enabled"})
    with pytest.raises(Exception):
        admin_s3.put_bucket_versioning(Bucket=made, VersioningConfiguration={"Status": "Off"})
    assert row_for(made)["versioning"] == "ENABLED"


def test_a_default_retention_rule_needs_a_bucket_that_can_hold_one(admin_s3, made):
    """`409 InvalidBucketState` on a bucket whose lock was never enabled.

    A rule the bucket can never enforce is the worst way to learn object
    lock is off, so it is refused rather than stored — and the refusal is
    middleware's own rule reaching the wire, since the row is what would
    have carried it.
    """
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
    """A longer rule is a registry row the S3 service refuses whole-file,
    so accepting it would answer `200` and take the service out at the
    next config read."""
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

        # And the value one day inside the ceiling is taken, so the
        # refusal above is the bound and not the feature.
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
