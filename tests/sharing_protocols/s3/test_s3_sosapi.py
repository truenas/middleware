"""The reserved SOSAPI names: two keys the server answers for itself.

Veeam's Smart Object Storage API is two documents under a fixed reserved
prefix, served from the server on every bucket rather than stored in
one. `capacity.xml` is the bucket dataset's own statfs taken when it is
asked for, and `system.xml` declares what the storage can do — including
a block-size recommendation derived from the dataset's `recordsize`.

`test_the_sosapi_block_size_follows_the_recordsize` moved here from
``tests/api2/test_s3_bucket.py``. It is the wiring case of the pair:
nothing about the block size is stored, so tuning the dataset changes
the recommendation at the next ask with no reload and no restart — which
is only observable over the protocol.
"""

import email.utils
import re
import time

from middlewared.test.integration.assets.s3 import s3_account, s3_bucket, s3_pids, s3_service, user_grant
from middlewared.test.integration.utils import pool, ssh
import pytest
from s3_client import client_for

SYSTEM = ".system-d26a9498-cb7c-4a87-a44a-8ae204f5ba6c/system.xml"
CAPACITY = ".system-d26a9498-cb7c-4a87-a44a-8ae204f5ba6c/capacity.xml"

DATASET = f"{pool}/s3proto-sosapi"
BUCKET = "s3proto-sosapi"


def counts(body: str) -> dict[str, int]:
    return {tag: int(re.search(f"<{tag}>(-?\\d+)</{tag}>", body).group(1)) for tag in ("Capacity", "Available", "Used")}


def served_at(got) -> float:
    """The `Last-Modified` the answer carried, in unix seconds."""
    stamp = got["ResponseMetadata"]["HTTPHeaders"]["last-modified"]
    return email.utils.parsedate_to_datetime(stamp).timestamp()


def test_the_system_document_declares_every_capability(s3, bucket):
    """All four, never omitted.

    The protocol's schema makes each one mandatory, so a capability this
    server does not implement is a `false` a reader can see rather than
    an absence they have to infer.
    """
    got = s3.get_object(Bucket=bucket, Key=SYSTEM)
    body = got["Body"].read().decode()
    assert got["ContentType"] == "application/xml"
    assert '<ProtocolVersion>"1.0"</ProtocolVersion>' in body
    assert "<CapacityInfo>true</CapacityInfo>" in body
    assert "<UploadSessions>false</UploadSessions>" in body
    assert "<EnableOnPremArchiveTier>false</EnableOnPremArchiveTier>" in body

    head = s3.head_object(Bucket=bucket, Key=SYSTEM)
    assert head["ETag"] == got["ETag"]
    assert head["ContentLength"] == len(body)


def test_iamsts_is_false_and_carries_no_endpoints(s3, bucket):
    """The capability asserts the *storage* serves a subset of IAM and
    STS. Nothing in this appliance does — not the daemon, not the
    middleware beside it — so it is false, no configuration can say
    otherwise, and the endpoint section the protocol would then make
    mandatory is never emitted."""
    body = s3.get_object(Bucket=bucket, Key=SYSTEM)["Body"].read().decode()
    assert "<IAMSTS>false</IAMSTS>" in body
    assert "APIEndpoints" not in body


@pytest.mark.parametrize("key", [SYSTEM, CAPACITY], ids=["system", "capacity"])
def test_the_documents_are_stamped_with_the_moment_they_were_served(s3, bucket, key):
    """The rule is the protocol's: a document whose `Last-Modified` is
    over ten minutes old makes the backup server assume the data is
    outdated and drop to non-SOSAPI processing — silently, with no error
    and no capacity in its interface.

    A synthesized answer cannot go stale, and this is what says so.
    """
    before = time.time()
    got = s3.get_object(Bucket=bucket, Key=key)
    got["Body"].read()
    after = time.time()
    # Whole seconds on the wire, so the window is the request's own,
    # widened by the stamp's resolution at each end.
    assert before - 1 <= served_at(got) <= after + 1, key


def test_the_capacity_document_is_the_dataset_answering(s3, bucket):
    got = counts(s3.get_object(Bucket=bucket, Key=CAPACITY)["Body"].read().decode())
    assert got["Capacity"] > 0
    assert got["Used"] + got["Available"] == got["Capacity"]


def test_the_names_answer_on_every_bucket(s3, buckets):
    """On every bucket the format says — including the versioned, locked
    one, where the answer carries no version id."""
    got = s3.get_object(Bucket=buckets["locked"], Key=SYSTEM)
    assert '<ProtocolVersion>"1.0"</ProtocolVersion>' in got["Body"].read().decode()
    assert "VersionId" not in got


def test_a_stored_object_is_shadowed(s3, bucket):
    """A write under the reserved name stores a real object; the read
    keeps answering the synthetic document, before and after that object
    is deleted."""
    s3.put_object(Bucket=bucket, Key=SYSTEM, Body=b"shadowed")
    body = s3.get_object(Bucket=bucket, Key=SYSTEM)["Body"].read()
    assert body != b"shadowed" and b"ProtocolVersion" in body

    s3.delete_object(Bucket=bucket, Key=SYSTEM)
    assert b"ProtocolVersion" in s3.get_object(Bucket=bucket, Key=SYSTEM)["Body"].read()


# ── the recommendation follows the dataset, live ─────────────────────


@pytest.fixture(scope="module")
def veeam():
    with s3_account("s3protoveeam") as account:
        yield account


def test_the_sosapi_block_size_follows_the_recordsize(veeam, daemon):
    """Moved from ``tests/api2/test_s3_bucket.py``.

    Nothing about the block size is stored: the daemon reads the
    dataset's `recordsize` when Veeam asks for `system.xml`, so tuning
    the dataset changes the recommendation at the next ask — with no
    reload and no restart, which the pid assertion is what proves.
    ZFS's 128K default recommends nothing.
    """
    with (
        s3_bucket(
            BUCKET,
            dataset=DATASET,
            owner=veeam.username,
            object_ownership="OBJECT_WRITER",
            grants=[user_grant(veeam.uid)],
        ),
        s3_service(),
    ):
        pid = s3_pids()
        s3 = client_for(veeam.key, daemon)

        def system_xml():
            return s3.get_object(Bucket=BUCKET, Key=SYSTEM)["Body"].read().decode()

        assert "SystemRecommendations" not in system_xml()

        ssh(f"zfs set recordsize=1M {DATASET}")
        assert "<SystemRecommendations><KbBlockSize>1024</KbBlockSize></SystemRecommendations>" in system_xml()

        ssh(f"zfs set recordsize=2M {DATASET}")
        assert "<KbBlockSize>4096</KbBlockSize>" in system_xml()

        ssh(f"zfs inherit recordsize {DATASET}")
        assert "SystemRecommendations" not in system_xml()

        assert s3_pids() == pid, "the recommendation is read per request, not registered"


def test_a_quota_clamps_the_reported_capacity(veeam, daemon):
    """ZFS answers statfs per dataset and clamps the counts to its quota,
    which is what makes the report the number an operator set rather than
    the pool's size.

    The bucket's own dataset carries the quota, so the document a backup
    client reads is the one its administrator meant it to see.
    """
    with (
        s3_bucket(
            BUCKET,
            dataset=DATASET,
            owner=veeam.username,
            object_ownership="OBJECT_WRITER",
            grants=[user_grant(veeam.uid)],
        ),
        s3_service(),
    ):
        ssh(f"zfs set quota=64M {DATASET}")
        s3 = client_for(veeam.key, daemon)
        got = counts(s3.get_object(Bucket=BUCKET, Key=CAPACITY)["Body"].read().decode())
        # The ceiling only needs to sit far under the pool's size to
        # prove the clamp happened.
        assert 0 < got["Capacity"] <= 128 * 1024 * 1024, got
