"""The snapshot layer: a bucket's own ZFS snapshots served as versions.

`snapshot_versions` is a list of patterns over the bucket dataset's
snapshot names, and every snapshot a pattern selects serves each object's
state frozen in it as a read-only version — listed by
`ListObjectVersions` and read by its version id. It composes with every
versioning state, which is why it is proved against two rows here: one
`SUSPENDED`, where ZFS holds the history beside the object tree's own,
and one never-versioned, which is ZFS history alone behind the empty
versioning document.

`test_snapshots_serve_as_versions` moved here from
``tests/api2/test_s3_bucket.py``; what is left of it is the listing cap,
which is a registry field and therefore a restart, on a bucket of its
own. The rest of the file is the layer's conformance.

**The name cache shapes this module.** A bucket's snapshot set is cached
for minutes once a `?versions` listing reads it, so every snapshot a
listing case relies on is made by the module fixture *before* the first
listing, and the destroy probe — which is the drop-and-invalidate path —
runs last. A point read by id is gated by the row's pattern alone and
never consults the cache.
"""

import contextlib
import time

from middlewared.test.integration.assets.s3 import s3_account, s3_bucket, s3_pids, s3_service, user_grant
from middlewared.test.integration.utils import call, pool
import pytest
from s3_client import client_for, code_of, drain, status_of

DATASET = f"{pool}/s3proto-snapcap"
BUCKET = "s3proto-snapcap"


def snapshot_id(name: str) -> str:
    """The wire id of a snapshot-derived version: `zfs.` then the name in
    lowercase hex.

    The name is the whole of it. A creation instant would say when a
    state was frozen, but it is readable only from the *unmounted* stub —
    once anything crosses into a snapshot the path answers from the
    frozen root — so an id carrying one would depend on what happens to
    be mounted.
    """
    return "zfs." + name.encode().hex()


def dataset_of(bucket: str) -> str:
    return call("sharing.s3.query", [["name", "=", bucket]], {"get": True})["dataset"]


def take(dataset: str, name: str) -> None:
    call("zfs.resource.snapshot.create", {"dataset": dataset, "name": name})


def destroy(dataset: str, name: str) -> None:
    """Destroy one snapshot, riding out a transient busy.

    A snapshot a reader crossed into is mounted, and its unmount can
    trail the reader by a moment. Retention middleware retries exactly
    like this.
    """
    for attempt in range(5):
        try:
            call("zfs.resource.snapshot.destroy", {"path": f"{dataset}@{name}", "recursive": True})
            return
        except Exception:
            if attempt == 4:
                raise
            time.sleep(1)


# ── the suspended row ────────────────────────────────────────────────


@pytest.fixture(scope="module")
def history(buckets, s3):
    """The suspended, snapshot-selecting bucket, or a skip."""
    name = buckets.get("history")
    if not name:
        pytest.skip("no suspended bucket: the session could not provision one")
    return name, dataset_of(name)


@pytest.fixture(scope="module")
def frozen(s3, history):
    """The module's history, made before any listing can cache it.

    Three snapshots: `s3-alpha` and `s3-beta` are selected by the row's
    `s3-*`, `manual-keep` is not. Between them: `k1` changes per
    snapshot, `k-stable` is identical in both and differs from live —
    the collapse's case — and `gone.txt` and `old/x.txt` exist only in
    `s3-alpha` and are deleted live behind null markers.
    """
    bucket, dataset = history
    drain(s3, bucket)
    made = []
    try:
        s3.put_object(Bucket=bucket, Key="k1", Body=b"alpha state")
        s3.put_object(Bucket=bucket, Key="k-stable", Body=b"stable frozen")
        s3.put_object(Bucket=bucket, Key="gone.txt", Body=b"gone bytes")
        s3.put_object(Bucket=bucket, Key="old/x.txt", Body=b"x frozen")
        take(dataset, "s3-alpha")
        made.append("s3-alpha")
        s3.put_object(Bucket=bucket, Key="k1", Body=b"beta state")
        take(dataset, "s3-beta")
        made.append("s3-beta")
        take(dataset, "manual-keep")
        made.append("manual-keep")
        s3.put_object(Bucket=bucket, Key="k1", Body=b"live state")
        s3.put_object(Bucket=bucket, Key="k-stable", Body=b"stable live")
        s3.delete_object(Bucket=bucket, Key="gone.txt")
        s3.delete_object(Bucket=bucket, Key="old/x.txt")
        yield {"bucket": bucket, "dataset": dataset, "snapshots": made}
    finally:
        # The snapshots first: leaving them would make the next run's
        # `s3-*` set ambiguous.
        for name in made:
            with contextlib.suppress(Exception):
                destroy(dataset, name)
        drain(s3, bucket)


def test_a_frozen_state_serves_by_its_id(s3, frozen):
    bucket = frozen["bucket"]
    alpha, beta = snapshot_id("s3-alpha"), snapshot_id("s3-beta")

    got = s3.get_object(Bucket=bucket, Key="k1", VersionId=alpha)
    assert got["Body"].read() == b"alpha state"
    assert got["VersionId"] == alpha

    head = s3.head_object(Bucket=bucket, Key="k1", VersionId=beta)
    assert head["VersionId"] == beta
    assert head["ContentLength"] == len(b"beta state")

    # The live read is untouched beside them.
    assert s3.get_object(Bucket=bucket, Key="k1")["Body"].read() == b"live state"


@pytest.mark.parametrize(
    "vid,why",
    [
        ("zfs.6D", "a malformed payload could name no version"),
        (snapshot_id("manual-keep"), "the pattern is the authority"),
        (snapshot_id("s3-never-made"), "a snapshot that does not exist"),
    ],
)
def test_screens_answer_no_such_version(s3, frozen, vid, why):
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=frozen["bucket"], Key="k1", VersionId=vid)
    assert status_of(caught.value) == 404, why
    assert code_of(caught.value) == "NoSuchVersion", why


@pytest.mark.parametrize("bypass", [False, True])
def test_destroying_a_frozen_state_is_denied(s3, frozen, bypass):
    """The snapshot is the hold: a version ZFS froze cannot be destroyed
    through S3 under any bypass, because the bypass is about retention
    and this is about the snapshot."""
    with pytest.raises(Exception) as caught:
        s3.delete_object(
            Bucket=frozen["bucket"],
            Key="k1",
            VersionId=snapshot_id("s3-alpha"),
            BypassGovernanceRetention=bypass,
        )
    assert status_of(caught.value) == 403
    assert code_of(caught.value) == "AccessDenied"


def test_a_named_delete_of_an_absent_key_in_a_snapshot_is_gone(s3, frozen):
    """Gone is the honest answer, not a refusal."""
    with pytest.raises(Exception) as caught:
        s3.delete_object(Bucket=frozen["bucket"], Key="never-existed", VersionId=snapshot_id("s3-alpha"))
    assert code_of(caught.value) == "NoSuchVersion"


def test_writing_a_frozen_state_is_denied(s3, frozen):
    """A snapshot version is read-only, so any write naming its id is
    `AccessDenied` — the same hold a destroy meets, and not a 501: the
    refusal needs no frozen-record read. A selected-but-absent snapshot
    is `NoSuchVersion`, exactly as the destroy answers."""
    bucket = frozen["bucket"]
    alpha = snapshot_id("s3-alpha")

    for write in (
        lambda vid: s3.put_object_tagging(
            Bucket=bucket, Key="k1", VersionId=vid, Tagging={"TagSet": [{"Key": "k", "Value": "v"}]}
        ),
        lambda vid: s3.delete_object_tagging(Bucket=bucket, Key="k1", VersionId=vid),
    ):
        with pytest.raises(Exception) as caught:
            write(alpha)
        assert status_of(caught.value) == 403, "a snapshot version is read-only"
        assert code_of(caught.value) == "AccessDenied"

    with pytest.raises(Exception) as caught:
        s3.put_object_tagging(
            Bucket=bucket,
            Key="k1",
            VersionId=snapshot_id("s3-never-made"),
            Tagging={"TagSet": [{"Key": "k", "Value": "v"}]},
        )
    assert code_of(caught.value) == "NoSuchVersion"


def test_the_listing_interleaves_frozen_history(s3, frozen):
    bucket = frozen["bucket"]
    alpha, beta = snapshot_id("s3-alpha"), snapshot_id("s3-beta")
    page = s3.list_object_versions(Bucket=bucket)
    rows = page.get("Versions", [])
    markers = page.get("DeleteMarkers", [])

    def of(key):
        return [row for row in rows if row["Key"] == key]

    # k1: the live null plus one row per changed frozen state.
    ids = [row["VersionId"] for row in of("k1")]
    assert "null" in ids, ids
    assert alpha in ids, ids
    assert beta in ids, ids

    # The unselected snapshot contributes nothing anywhere.
    assert not any(row["VersionId"] == snapshot_id("manual-keep") for row in rows)

    # k-stable is identical in both snapshots, so the collapse names one
    # row, under the oldest holder.
    stable = [row["VersionId"] for row in of("k-stable")]
    assert stable.count(alpha) == 1, stable
    assert beta not in stable, stable

    # Deleted keys are found through the union, their markers beside
    # them; a snapshot row never elects latest and always carries an ETag.
    assert of("gone.txt"), "the union finds a deleted key"
    assert any(m["Key"] == "gone.txt" for m in markers), markers
    assert of("old/x.txt"), "a deleted prefix's key is found"
    for row in rows:
        if row["VersionId"].startswith("zfs."):
            assert not row["IsLatest"], row
            assert row.get("ETag"), row


def test_a_snapshot_only_prefix_still_lists(s3, frozen):
    page = s3.list_object_versions(Bucket=frozen["bucket"], Prefix="old/")
    assert "old/x.txt" in [row["Key"] for row in page.get("Versions", [])]


def test_a_destroyed_snapshot_drops_from_the_listing(s3, frozen):
    """Last on purpose: it invalidates the module's cached set.

    The destroy force-unmounts the snapshot a listing just crossed into,
    the next page meets the absence, drops the snapshot and the cache
    entry with it, and the one after lists from the refreshed set — never
    an error, and never a page claiming the rows still stand.
    """
    bucket, dataset = frozen["bucket"], frozen["dataset"]
    alpha, beta = snapshot_id("s3-alpha"), snapshot_id("s3-beta")
    destroy(dataset, "s3-beta")
    frozen["snapshots"].remove("s3-beta")

    deadline = time.monotonic() + 30
    while True:
        ids = [row["VersionId"] for row in s3.list_object_versions(Bucket=bucket).get("Versions", [])]
        if beta not in ids:
            break
        assert time.monotonic() < deadline, ids
        time.sleep(1)

    # The survivor still serves, list and point read both.
    assert alpha in ids, ids
    assert s3.get_object(Bucket=bucket, Key="k1", VersionId=alpha)["Body"].read() == b"alpha state"

    # And the destroyed one is gone, not unavailable.
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key="k1", VersionId=beta)
    assert code_of(caught.value) == "NoSuchVersion"

    # **The aliasing a name-only id accepts**, pinned rather than left to
    # be discovered: remade under the same name the snapshot is a
    # different point in time, and the id that named the destroyed one
    # now serves the new one.
    take(dataset, "s3-beta")
    frozen["snapshots"].append("s3-beta")
    assert s3.get_object(Bucket=bucket, Key="k1", VersionId=beta)["Body"].read() == b"live state"


# ── the never-versioned selecting row ────────────────────────────────


@pytest.fixture(scope="module")
def attic(buckets, s3):
    name = buckets.get("attic")
    if not name:
        pytest.skip("no attic bucket: the session could not provision one")
    return name, dataset_of(name)


@pytest.fixture(scope="module")
def attic_frozen(s3, attic):
    """One selected snapshot and one unselected: `k1` changes after the
    freeze, `doomed` is deleted live — outside versioning, so nothing
    marks it — and `manual-x` proves the pattern is the authority on this
    row too."""
    bucket, dataset = attic
    drain(s3, bucket)
    made = []
    try:
        s3.put_object(Bucket=bucket, Key="k1", Body=b"first")
        s3.put_object(Bucket=bucket, Key="doomed", Body=b"was here")
        take(dataset, "s3-one")
        made.append("s3-one")
        take(dataset, "manual-x")
        made.append("manual-x")
        s3.put_object(Bucket=bucket, Key="k1", Body=b"second")
        s3.delete_object(Bucket=bucket, Key="doomed")
        yield {"bucket": bucket, "dataset": dataset}
    finally:
        for name in made:
            with contextlib.suppress(Exception):
                destroy(dataset, name)
        drain(s3, bucket)


def test_the_attic_reports_the_empty_document(s3, attic):
    """The report is the mutation contract told straight: this row's
    writes mint nothing and its deletes leave nothing, exactly the
    never-versioned answer — the history rides beside it."""
    assert "Status" not in s3.get_bucket_versioning(Bucket=attic[0])


def test_the_attic_lists_zfs_history_alone(s3, attic_frozen):
    bucket = attic_frozen["bucket"]
    one = snapshot_id("s3-one")
    page = s3.list_object_versions(Bucket=bucket)
    rows = page.get("Versions", [])

    # A delete outside versioning leaves no marker anywhere.
    assert page.get("DeleteMarkers", []) == [], page.get("DeleteMarkers")

    k1 = {row["VersionId"]: row for row in rows if row["Key"] == "k1"}
    assert set(k1) == {"null", one}, k1
    assert k1["null"]["IsLatest"], k1
    assert not k1[one]["IsLatest"], k1

    doomed = [row for row in rows if row["Key"] == "doomed"]
    assert [row["VersionId"] for row in doomed] == [one], doomed
    assert not doomed[0]["IsLatest"], "the key currently has no latest"

    assert not any(row["VersionId"] == snapshot_id("manual-x") for row in rows)


def test_the_attic_serves_and_guards_frozen_state(s3, attic_frozen):
    bucket = attic_frozen["bucket"]
    one = snapshot_id("s3-one")

    got = s3.get_object(Bucket=bucket, Key="k1", VersionId=one)
    assert got["Body"].read() == b"first"
    assert got["VersionId"] == one

    # The deleted key is gone live, and only live.
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key="doomed")
    assert code_of(caught.value) == "NoSuchKey"
    assert s3.get_object(Bucket=bucket, Key="doomed", VersionId=one)["Body"].read() == b"was here"

    # Read-only on this row too, through both delete verbs.
    with pytest.raises(Exception) as caught:
        s3.delete_object(Bucket=bucket, Key="k1", VersionId=one)
    assert status_of(caught.value) == 403
    assert code_of(caught.value) == "AccessDenied"

    answered = s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": "k1", "VersionId": one}]})
    assert answered.get("Deleted", []) == [], answered
    assert [(e["Key"], e.get("VersionId"), e["Code"]) for e in answered.get("Errors", [])] == [
        ("k1", one, "AccessDenied")
    ], answered
    assert s3.get_object(Bucket=bucket, Key="k1")["Body"].read() == b"second"


# ── the listing cap, which is a registry change ──────────────────────


@pytest.fixture(scope="module")
def capped_owner():
    with s3_account("s3protosnap") as account:
        yield account


def test_the_listing_cap_bounds_the_listing_and_not_the_id(capped_owner, daemon):
    """Moved from ``tests/api2/test_s3_bucket.py``.

    `snapshot_versions_max` is read at registration, so moving it is a
    restart rather than a reload — and what it bounds is the *listing*
    alone: a selected snapshot past the cap still serves by its version
    id, which is what keeps a bounded page from being a bounded history.
    """
    with (
        s3_bucket(
            BUCKET,
            dataset=DATASET,
            owner=capped_owner.username,
            object_ownership="OBJECT_WRITER",
            versioning="SUSPENDED",
            snapshot_versions=["s3-*"],
            grants=[user_grant(capped_owner.uid)],
        ) as entry,
        s3_service(),
    ):
        made = []
        try:
            s3 = client_for(capped_owner.key, daemon)
            s3.put_object(Bucket=BUCKET, Key="k1", Body=b"alpha state")
            take(DATASET, "s3-alpha")
            made.append("s3-alpha")
            s3.put_object(Bucket=BUCKET, Key="k1", Body=b"beta state")
            take(DATASET, "s3-beta")
            made.append("s3-beta")
            s3.put_object(Bucket=BUCKET, Key="k1", Body=b"live state")

            alpha, beta = snapshot_id("s3-alpha"), snapshot_id("s3-beta")
            assert entry["snapshot_versions_max"] == 64
            ids = [v["VersionId"] for v in s3.list_object_versions(Bucket=BUCKET).get("Versions", [])]
            assert alpha in ids and beta in ids, ids

            pid = s3_pids()
            call("sharing.s3.update", entry["id"], {"snapshot_versions_max": 1})
            assert s3_pids() != pid, "the listing cap is a registry field, so a restart"

            ids = [v["VersionId"] for v in s3.list_object_versions(Bucket=BUCKET).get("Versions", [])]
            assert beta in ids and alpha not in ids, ids
            # Past the cap and still addressable, which is the point.
            assert s3.get_object(Bucket=BUCKET, Key="k1", VersionId=alpha)["Body"].read() == b"alpha state"
        finally:
            for name in made:
                with contextlib.suppress(Exception):
                    destroy(DATASET, name)
