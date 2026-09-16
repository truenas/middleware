"""`x-amz-checksum-*`: what is verified at ingest and served back.

Modern botocore sends `x-amz-checksum-crc32` on every upload and asks
for it back on every read, both by default, so the round trip below is
what an unconfigured SDK already does. What is *not* reachable that way
is an object written with no checksum at all — that needs the
`s3_unsummed` client, which is why the fixture exists.

Nothing is minted: a write that sent none stores none, and the object
answers no checksum for the rest of its life. Withholding a stale value
is only safe because the absence is expressible.
"""

import base64
import binascii
import hashlib

import pytest
from s3_client import code_of, payload, status_of

PREFIX = "sum/"


def test_a_declared_checksum_is_verified_echoed_and_served(s3, bucket):
    key = f"{PREFIX}crc32.bin"
    body = payload(4096)
    want = base64.b64encode(binascii.crc32(body).to_bytes(4, "big")).decode()

    put = s3.put_object(Bucket=bucket, Key=key, Body=body)
    assert put.get("ChecksumCRC32") == want, "the write echoes what it verified"

    got = s3.get_object(Bucket=bucket, Key=key, ChecksumMode="ENABLED")
    got["Body"].read()
    assert got.get("ChecksumCRC32") == want, "the read answers the stored one"
    assert got.get("ChecksumType") == "FULL_OBJECT", got.get("ChecksumType")

    head = s3.head_object(Bucket=bucket, Key=key, ChecksumMode="ENABLED")
    assert head.get("ChecksumCRC32") == want, "head answers it too"


def test_a_write_that_sent_none_stores_none(s3, s3_unsummed, bucket):
    """And the object still reads — the absence is what makes withholding
    a stale value safe rather than a silent lie."""
    key = f"{PREFIX}none.bin"
    s3_unsummed.put_object(Bucket=bucket, Key=key, Body=b"plain")

    bare = s3.get_object(Bucket=bucket, Key=key, ChecksumMode="ENABLED")
    bare["Body"].read()
    assert bare.get("ChecksumCRC32") is None, bare.get("ChecksumCRC32")
    assert bare["ContentLength"] == 5


#: `CRC32C` is absent on purpose: asking botocore to *compute* one needs
#: the `botocore[crt]` extra, which the test runner does not install, and
#: a case that required it would fail for the runner rather than for the
#: server. The wire lane is still covered — `test_a_wrong_checksum_is_bad_digest`
#: sends a literal `x-amz-checksum-crc32c`, which the server verifies and
#: the client never computes.
COMPUTED = ["CRC32", "SHA1", "SHA256"]


@pytest.mark.parametrize("algorithm", COMPUTED)
def test_each_algorithm_round_trips(s3, bucket, algorithm):
    """A client picks the algorithm; the object answers the one it was
    given and no other."""
    key = f"{PREFIX}{algorithm.lower()}.bin"
    field = f"Checksum{algorithm}"
    put = s3.put_object(Bucket=bucket, Key=key, Body=payload(1024), ChecksumAlgorithm=algorithm)
    assert put.get(field), put

    got = s3.head_object(Bucket=bucket, Key=key, ChecksumMode="ENABLED")
    assert got.get(field) == put[field]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"ChecksumCRC32": "AAAAAA=="},
        {"ChecksumCRC32C": "AAAAAA=="},
        {"ChecksumSHA1": base64.b64encode(b"\0" * 20).decode()},
        {"ChecksumSHA256": base64.b64encode(b"\0" * 32).decode()},
    ],
    ids=["crc32", "crc32c", "sha1", "sha256"],
)
def test_a_wrong_checksum_is_bad_digest(s3, bucket, kwargs):
    """Every lane the entity stage verifies refuses the same way.

    One algorithm passing while another silently stored an unverified
    body is the failure this covers, so the parametrization is the point
    rather than any single case.
    """
    with pytest.raises(Exception) as caught:
        s3.put_object(Bucket=bucket, Key=f"{PREFIX}wrong.bin", Body=b"x", **kwargs)
    assert status_of(caught.value) == 400
    assert code_of(caught.value) == "BadDigest", kwargs


def test_a_listing_row_reports_the_checksum_the_write_declared(s3, bucket):
    """`ChecksumAlgorithm` and `ChecksumType` are elements of a v2
    listing row, and the row's own read makes them cheap — the values sit
    on the record it already reads for its ETag.

    Two algorithms rather than one, because a hardcoded value would
    satisfy either alone.
    """
    crc, sha = f"{PREFIX}listck-crc.bin", f"{PREFIX}listck-sha.bin"
    s3.put_object(Bucket=bucket, Key=crc, Body=b"body")
    s3.put_object(Bucket=bucket, Key=sha, Body=b"body", ChecksumAlgorithm="SHA256")

    rows = {row["Key"]: row for row in s3.list_objects_v2(Bucket=bucket, Prefix=f"{PREFIX}listck-")["Contents"]}
    assert rows[crc].get("ChecksumAlgorithm") == ["CRC32"], rows[crc]
    assert rows[sha].get("ChecksumAlgorithm") == ["SHA256"], rows[sha]
    for row in (rows[crc], rows[sha]):
        assert row.get("ChecksumType") == "FULL_OBJECT", row


def test_a_row_omits_the_elements_where_nothing_was_checksummed(s3_unsummed, bucket):
    """Always emitting would name an algorithm no client asked for, and
    nothing is minted for a write that sent none."""
    key = f"{PREFIX}listck-bare.bin"
    s3_unsummed.put_object(Bucket=bucket, Key=key, Body=b"body")

    row = next(r for r in s3_unsummed.list_objects_v2(Bucket=bucket, Prefix=key)["Contents"] if r["Key"] == key)
    assert "ChecksumAlgorithm" not in row, row
    assert "ChecksumType" not in row, row


def test_a_multipart_composes_the_declared_checksum(s3, bucket):
    """A `COMPOSITE` checksum over the parts' own, which is the shape a
    backup product declares at the create and reads off the assembled
    object — never an ETag."""
    key = f"{PREFIX}composed.bin"
    bodies = [b"\x01" * (5 * 1024 * 1024), b"the last part is exempt from the floor"]
    uid = s3.create_multipart_upload(Bucket=bucket, Key=key, ChecksumAlgorithm="SHA256", ChecksumType="COMPOSITE")[
        "UploadId"
    ]

    parts = []
    for number, body in enumerate(bodies, start=1):
        digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
        out = s3.upload_part(
            Bucket=bucket,
            Key=key,
            UploadId=uid,
            PartNumber=number,
            Body=body,
            ChecksumAlgorithm="SHA256",
            ChecksumSHA256=digest,
        )
        assert out["ChecksumSHA256"] == digest, f"part {number} kept its checksum"
        parts.append({"ETag": out["ETag"], "PartNumber": number, "ChecksumSHA256": digest})

    done = s3.complete_multipart_upload(Bucket=bucket, Key=key, UploadId=uid, MultipartUpload={"Parts": parts})
    joined = b"".join(hashlib.sha256(b).digest() for b in bodies)
    want = base64.b64encode(hashlib.sha256(joined).digest()).decode()
    assert done["ChecksumSHA256"] == f"{want}-{len(bodies)}", done
