"""The ETag: what it is by default, and the bucket row that changes it.

A plain write's ETag is a drawn token rather than a content digest — the
object was never hashed, and this format commits to that. Two client
escapes are pinned because they are independent: s3cmd looks for a `-`
anywhere in the value, rclone matches the whole value against
`^[0-9a-f]{32}$`, and a token has to fail both tests for a client to
know it is not an MD5.

A *multipart* object's ETag is AWS's composite by default: the MD5 of
the part MD5s with the part count appended, which costs an MD5 pass over
every part at ingest. `multipart_etag = MINTED` is a bucket-level
assertion that nothing writing the bucket reads its ETags, and that row
is proved beside one that does not carry it — the answer is per bucket
and a single row cannot show both.
"""

import base64
import hashlib

import pytest
from s3_client import drain

PREFIX = "etag/"
PART = 5 * 1024 * 1024


def composite(bodies):
    """AWS's construction, as a client would redo it."""
    joined = b"".join(hashlib.md5(b).digest() for b in bodies)
    return f'"{hashlib.md5(joined).hexdigest()}-{len(bodies)}"'


def parts_of():
    """Two parts: the first over the 5 MiB floor, the second exempt."""
    return [b"\x01" * PART, b"the last part is exempt from the floor"]


def upload(s3, bucket, key, bodies, content_md5=False):
    """Run one multipart upload, returning the part ETags and the
    object's."""
    uid = s3.create_multipart_upload(Bucket=bucket, Key=key)["UploadId"]
    parts, etags = [], []
    for number, body in enumerate(bodies, start=1):
        extra = {}
        if content_md5:
            extra["ContentMD5"] = base64.b64encode(hashlib.md5(body).digest()).decode()
        out = s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=number, Body=body, **extra)
        etags.append(out["ETag"])
        parts.append({"ETag": out["ETag"], "PartNumber": number})
    done = s3.complete_multipart_upload(Bucket=bucket, Key=key, UploadId=uid, MultipartUpload={"Parts": parts})
    return etags, done["ETag"]


# ── the default shape ────────────────────────────────────────────────


def test_a_plain_write_mints_a_token_rather_than_a_digest(s3, bucket):
    key = f"{PREFIX}shape.bin"
    etag = s3.put_object(Bucket=bucket, Key=key, Body=b"x")["ETag"].strip('"')
    groups = etag.split("-")

    assert [len(g) for g in groups] == [8, 4, 4, 4, 12], etag
    assert all(c in "0123456789abcdef" for g in groups for c in g), etag
    assert groups[2][0] == "4", f"version 4: {etag}"
    assert groups[3][0] in "89ab", f"RFC 9562 variant: {etag}"

    # The two client escapes, which are independent tests.
    assert "-" in etag, "s3cmd's escape: the value carries a dash"
    assert len(etag) != 32, "rclone's escape: not the bare MD5 length"
    assert etag != hashlib.md5(b"x").hexdigest(), "not a content digest"


def test_the_default_bucket_composes_a_multipart_etag(s3, bucket):
    """The control for the minted row below: real part digests and AWS's
    own composite, so what that row changes is the row and not the
    build."""
    key = f"{PREFIX}control.bin"
    bodies = parts_of()
    try:
        etags, etag = upload(s3, bucket, key, bodies)
        for part_etag, body in zip(etags, bodies):
            assert part_etag.strip('"') == hashlib.md5(body).hexdigest()
        assert etag == composite(bodies)
    finally:
        drain(s3, bucket, PREFIX)


# ── the minted row ───────────────────────────────────────────────────


@pytest.fixture(scope="module")
def minted(buckets):
    name = buckets.get("minted")
    if not name:
        pytest.skip("no minted bucket: the session could not provision one")
    return name


@pytest.fixture
def key(s3, minted):
    drain(s3, minted, PREFIX)
    yield f"{PREFIX}obj.bin"
    drain(s3, minted, PREFIX)


def test_a_part_is_not_hashed_and_says_so(s3, minted, key):
    """No client reason to hash, so each part ETag is a token — still 32
    hex, because Complete matches the manifest against that shape and a
    part ETag has no other form available."""
    bodies = parts_of()
    etags, _ = upload(s3, minted, key, bodies)
    for number, (etag, body) in enumerate(zip(etags, bodies), start=1):
        bare = etag.strip('"')
        assert len(bare) == 32, f"part {number} still renders as 32 hex: {etag}"
        assert all(c in "0123456789abcdef" for c in bare), etag
        assert bare != hashlib.md5(body).hexdigest(), f"part {number} was hashed"


def test_the_object_answers_a_token_not_a_composite(s3, minted, key):
    """One unhashed part makes the composite unbuildable, so the object
    takes the minted arm."""
    bodies = parts_of()
    _, etag = upload(s3, minted, key, bodies)
    assert not etag.strip('"').endswith(f"-{len(bodies)}"), etag
    assert etag != composite(bodies)


def test_the_bytes_still_assemble(s3, minted, key):
    """Declining the digest changes what is answered, never what is
    stored."""
    bodies = parts_of()
    upload(s3, minted, key, bodies)
    got = s3.get_object(Bucket=minted, Key=key)["Body"].read()
    assert got == b"".join(bodies)
    assert s3.head_object(Bucket=minted, Key=key)["ContentLength"] == len(got)


def test_a_content_md5_is_still_a_reason_to_hash(s3, minted, key):
    """The arm that keeps a hash-checking client whole on a minted row.

    A `Content-MD5` on the part is verified either way, and the digest it
    verified against is then the part's ETag — so a client that sends one
    gets real part digests and AWS's composite back, on the same bucket
    that declined them above.
    """
    bodies = parts_of()
    etags, etag = upload(s3, minted, key, bodies, content_md5=True)
    for number, (part_etag, body) in enumerate(zip(etags, bodies), start=1):
        assert part_etag.strip('"') == hashlib.md5(body).hexdigest(), f"part {number}"
    assert etag == composite(bodies), "so the composite is AWS's own"


def test_list_parts_echoes_whatever_the_upload_answered(s3, minted):
    """`ListParts` reads the same record `UploadPart` wrote, so the two
    agree on a minted row as they do on any other — which is what makes a
    resume-shaped client see a consistent, if unverifiable, ETag."""
    key = f"{PREFIX}listed.bin"
    bodies = parts_of()
    uid = s3.create_multipart_upload(Bucket=minted, Key=key)["UploadId"]
    try:
        answered = [
            s3.upload_part(Bucket=minted, Key=key, UploadId=uid, PartNumber=n, Body=body)["ETag"]
            for n, body in enumerate(bodies, start=1)
        ]
        listed = s3.list_parts(Bucket=minted, Key=key, UploadId=uid)["Parts"]
        assert [p["ETag"] for p in listed] == answered
        assert [p["PartNumber"] for p in listed] == [1, 2]
    finally:
        s3.abort_multipart_upload(Bucket=minted, Key=key, UploadId=uid)


def test_a_single_part_put_is_unchanged(s3, minted, key):
    """The row names the multipart ETag and nothing else: a plain PUT
    already minted its ETag on every bucket, so there is nothing here for
    this row to change."""
    body = b"single part"
    put = s3.put_object(Bucket=minted, Key=key, Body=body)
    assert put["ETag"].strip('"') != hashlib.md5(body).hexdigest()
    assert s3.get_object(Bucket=minted, Key=key)["Body"].read() == body


def test_a_declared_checksum_is_still_answered(s3, minted, key):
    """The deployment the row exists for still gets its checksum.

    The row declines the MD5 an ETag is built from, and nothing else. A
    part carries whatever checksum its client sent either way, so the
    composite over those is buildable and the client that declared it is
    owed the answer — withholding it here would take the value away from
    exactly the workload the row is for.
    """
    bodies = parts_of()
    uid = s3.create_multipart_upload(Bucket=minted, Key=key, ChecksumAlgorithm="SHA256", ChecksumType="COMPOSITE")[
        "UploadId"
    ]

    parts = []
    for number, body in enumerate(bodies, start=1):
        digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
        out = s3.upload_part(
            Bucket=minted,
            Key=key,
            UploadId=uid,
            PartNumber=number,
            Body=body,
            ChecksumAlgorithm="SHA256",
            ChecksumSHA256=digest,
        )
        assert out["ChecksumSHA256"] == digest, f"part {number} kept its checksum"
        parts.append({"ETag": out["ETag"], "PartNumber": number, "ChecksumSHA256": digest})

    done = s3.complete_multipart_upload(Bucket=minted, Key=key, UploadId=uid, MultipartUpload={"Parts": parts})
    joined = b"".join(hashlib.sha256(b).digest() for b in bodies)
    want = base64.b64encode(hashlib.sha256(joined).digest()).decode()
    assert done["ChecksumSHA256"] == f"{want}-{len(bodies)}", done
    # And the ETag is still the token: the two are independent.
    assert not done["ETag"].strip('"').endswith(f"-{len(bodies)}")
