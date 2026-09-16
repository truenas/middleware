"""`GetBucketVersioning`, and the one config-plane path back out of it.

The probe is what a backup client runs before it decides whether a
version id means anything, so answering "unversioned" from a bucket
whose writes mint ids would strand every one of them. The answer is the
registered row's, which is why it is asserted against three rows
configured differently rather than against one.

`test_force_disable_versioning_destroys_history` moved here from
``tests/api2/test_s3_bucket.py``. It is the whole workflow over the
wire — an enabled bucket accumulates versions and a delete marker, the
forced disable restarts the service, and every one of those ids stops
resolving — and only the restart half was ever about middleware.
"""

from middlewared.test.integration.assets.s3 import s3_account, s3_bucket, s3_pids, s3_service, user_grant
from middlewared.test.integration.utils import call, pool
import pytest
from s3_client import client_for, code_of

DATASET = f"{pool}/s3proto-versioning"
BUCKET = "s3proto-versioning"


def test_an_unversioned_bucket_reports_no_status(s3, bucket):
    """AWS has no spelling for "never versioned" but the absent element,
    and botocore surfaces that as a missing key rather than a falsy one —
    so the assertion is on absence."""
    answered = s3.get_bucket_versioning(Bucket=bucket)
    assert "Status" not in answered, answered.get("Status")


def test_a_versioned_bucket_reports_enabled(s3, buckets):
    locked = buckets["locked"]
    if not locked:
        pytest.skip("no versioned bucket: the session could not provision one")
    assert s3.get_bucket_versioning(Bucket=locked).get("Status") == "Enabled"


def test_a_suspended_bucket_reports_suspended(s3, buckets):
    history = buckets["history"]
    if not history:
        pytest.skip("no suspended bucket: the session could not provision one")
    assert s3.get_bucket_versioning(Bucket=history).get("Status") == "Suspended"


def test_a_suspended_write_returns_no_version_id(s3, buckets):
    """A suspended bucket's `PutObject` answers no `x-amz-version-id`.

    Worth pinning because the reference reads the other way at a glance:
    *"Suspended — all objects added to the bucket receive the version ID
    null"* is about the version the object gets, not about the response
    header, and the header's own description is "Version ID of the newly
    created object, in case the bucket has versioning turned on".
    Suspended is not turned on. A read of the same object does answer
    `null`, which is the object's version and not a contradiction.

    Identity and emission are separate — a suspended bucket mints an id
    either way — and this is the emission half.
    """
    bucket = buckets["history"]
    if not bucket:
        pytest.skip("no suspended bucket: the session could not provision one")

    answered = s3.put_object(Bucket=bucket, Key="suspended/no-id.bin", Body=b"body")
    assert "VersionId" not in answered, answered.get("VersionId")

    got = s3.get_object(Bucket=bucket, Key="suspended/no-id.bin")
    assert got["ResponseMetadata"]["HTTPHeaders"].get("x-amz-version-id") in (None, "null")


# ── the forced disable, end to end ───────────────────────────────────


@pytest.fixture(scope="module")
def historian():
    with s3_account("s3protovers") as account:
        yield account


def test_force_disable_versioning_destroys_history(historian, daemon):
    """The whole workflow over the wire.

    An enabled bucket accumulates two versions of one key and a delete
    marker over another; the forced disable restarts the service;
    versioning then reads never-enabled, the superseded id stops
    resolving, and the deleted key stays deleted. The version files'
    physical removal is the daemon's background sweep and is not waited
    on here.
    """
    with (
        s3_bucket(
            BUCKET,
            dataset=DATASET,
            owner=historian.username,
            object_ownership="OBJECT_WRITER",
            versioning="ENABLED",
            grants=[user_grant(historian.uid)],
        ) as entry,
        s3_service(),
    ):
        s3 = client_for(historian.key, daemon)
        s3.put_object(Bucket=BUCKET, Key="k1", Body=b"one")
        s3.put_object(Bucket=BUCKET, Key="k1", Body=b"two")
        s3.put_object(Bucket=BUCKET, Key="k2", Body=b"doomed")
        s3.delete_object(Bucket=BUCKET, Key="k2")

        assert s3.get_bucket_versioning(Bucket=BUCKET)["Status"] == "Enabled"
        listing = s3.list_object_versions(Bucket=BUCKET)
        assert len([v for v in listing["Versions"] if v["Key"] == "k1"]) == 2
        assert [m["Key"] for m in listing["DeleteMarkers"]] == ["k2"]
        superseded = next(v["VersionId"] for v in listing["Versions"] if v["Key"] == "k1" and not v["IsLatest"])

        pid = s3_pids()
        disabled = call("sharing.s3.force_disable_versioning", entry["id"])
        assert disabled["versioning"] == "OFF"
        assert s3_pids() != pid, "the forced disable is a restart"

        assert "Status" not in s3.get_bucket_versioning(Bucket=BUCKET)
        listing = s3.list_object_versions(Bucket=BUCKET)
        assert [(v["Key"], v["VersionId"]) for v in listing.get("Versions", [])] == [("k1", "null")]
        assert listing.get("DeleteMarkers", []) == []
        assert s3.get_object(Bucket=BUCKET, Key="k1")["Body"].read() == b"two"

        with pytest.raises(Exception) as caught:
            s3.get_object(Bucket=BUCKET, Key="k1", VersionId=superseded)
        assert code_of(caught.value) == "NoSuchVersion"
        with pytest.raises(Exception) as caught:
            s3.get_object(Bucket=BUCKET, Key="k2")
        assert code_of(caught.value) == "NoSuchKey"

        # Already off: the second call is an idempotent no-op — the row
        # stands and the service reloads rather than restarts.
        pid = s3_pids()
        assert call("sharing.s3.force_disable_versioning", entry["id"])["versioning"] == "OFF"
        assert s3_pids() == pid
