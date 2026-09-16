"""Instructions this server refuses rather than drops.

A `200` on a write is the client's whole statement that what it asked
for is what was stored. So an instruction with no implementation behind
it is answered where the client can see it — `501 NotImplemented`,
naming the surface — rather than being ignored under a success.

Every case sends the working request beside the refused one, so a `501`
is attributable to the instruction rather than to the request being
malformed in some way nobody noticed. And every refusal is followed by a
read: a refusal that had *already* written is the exact failure the rule
exists to prevent, and the status alone cannot tell the two apart.
"""

import base64
import hashlib

import pytest
from s3_client import raw_request

PREFIX = "refuse/"


def refused(resp, surface):
    assert resp.status_code == 501, resp.content[:200]
    assert b"NotImplemented" in resp.content, resp.content[:200]
    assert surface in resp.content, resp.content[:200]


def batch(s3, bucket, body):
    """A batch delete with the `Content-MD5` the operation requires."""
    digest = base64.b64encode(hashlib.md5(body).digest()).decode()
    return raw_request(s3, "POST", f"/{bucket}?delete", body=body, headers={"Content-MD5": digest})


# ── the conditional delete, in both its spellings ────────────────────


#: The three headers AWS defines for a conditional `DeleteObject`. Each
#: is checked on its own: a gate that stopped reading one of them would
#: still refuse the other two and look correct.
DELETE_HEADERS = [
    ("If-Match", '"a9b1c3d5e7f90123456789abcdef0123"'),
    ("x-amz-if-match-size", "4"),
    ("x-amz-if-match-last-modified-time", "Wed, 01 Jan 2025 00:00:00 GMT"),
]


@pytest.mark.parametrize("header,value", DELETE_HEADERS)
def test_a_conditional_delete_header_is_refused(s3, bucket, header, value):
    """`501`, and the key is still there afterwards.

    The second assertion is the one that matters: a server that read none
    of the header may answer only with a refusal, or it may execute
    unconditionally a delete the client made conditional — and behind a
    `501` those look identical.
    """
    key = f"{PREFIX}conditional.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"body")

    refused(
        raw_request(s3, "DELETE", f"/{bucket}/{key}", headers={header: value}),
        b"conditional DeleteObject",
    )
    assert s3.head_object(Bucket=bucket, Key=key)["ContentLength"] == 4

    # Unconditionally, the same DELETE removes it — so the refusal above
    # is the header and not the target.
    assert raw_request(s3, "DELETE", f"/{bucket}/{key}").status_code == 204


#: The three members an `<Object>` row may carry to make its own delete
#: conditional.
DELETE_MEMBERS = [
    ("ETag", '"a9b1c3d5e7f90123456789abcdef0123"'),
    ("Size", "4"),
    ("LastModifiedTime", "2025-01-01T00:00:00.000Z"),
]


@pytest.mark.parametrize("member,value", DELETE_MEMBERS)
def test_a_conditional_batch_row_is_refused(s3, bucket, member, value):
    """One conditional row refuses the whole manifest, and deletes none
    of it.

    Refusing the manifest rather than the row is the only safe reading: a
    batch that dropped the condition and honoured the row would delete an
    object the client asked to be spared, and one that skipped the row
    would answer `200` for a delete that never happened. This is the
    spelling with the widest blast radius — one manifest can carry a
    thousand of them.
    """
    keys = [f"{PREFIX}batch-a.bin", f"{PREFIX}batch-b.bin"]
    for key in keys:
        s3.put_object(Bucket=bucket, Key=key, Body=b"body")

    rows = f"<Object><Key>{keys[0]}</Key><{member}>{value}</{member}></Object><Object><Key>{keys[1]}</Key></Object>"
    refused(
        batch(s3, bucket, f"<Delete>{rows}</Delete>".encode()),
        b"conditional DeleteObjects members",
    )
    for key in keys:
        assert s3.head_object(Bucket=bucket, Key=key)["ContentLength"] == 4

    # The same manifest without the member deletes both, so what was
    # refused is the condition and not the shape of the document.
    plain = "".join(f"<Object><Key>{k}</Key></Object>" for k in keys)
    ok = batch(s3, bucket, f"<Delete>{plain}</Delete>".encode())
    assert ok.status_code == 200, ok.content[:200]
    for key in keys:
        assert b"<Deleted>" in ok.content and key.encode() in ok.content


# ── write headers naming a refused surface ───────────────────────────


#: Header, the value a client would send, and the surface the refusal
#: must name. Each of these has a sub-resource that answers `501`
#: already, so accepting the *header* spelling would let a refused
#: operation succeed through a side door.
UNHONORED = [
    ("x-amz-server-side-encryption", "AES256", b"encryption"),
    ("x-amz-server-side-encryption-aws-kms-key-id", "arn:aws:kms:us-east-1:1:key/x", b"encryption"),
    ("x-amz-website-redirect-location", "/elsewhere", b"website"),
]


@pytest.mark.parametrize("header,value,surface", UNHONORED)
def test_a_header_naming_a_refused_surface_is_refused(s3, bucket, header, value, surface):
    """`501`, naming the surface, and nothing stored.

    The encryption pair is the one worth stating plainly: a client whose
    policy requires encryption at rest, told its write succeeded.
    """
    key = f"{PREFIX}{header}.bin"
    resp = raw_request(s3, "PUT", f"/{bucket}/{key}", body=b"body", headers={header: value})
    assert resp.status_code == 501, resp.content[:200]
    assert surface in resp.content, resp.content[:200]

    with pytest.raises(Exception) as caught:
        s3.head_object(Bucket=bucket, Key=key)
    assert caught.value.response["ResponseMetadata"]["HTTPStatusCode"] == 404, f"{header} stored an object"


@pytest.mark.parametrize(
    "value,ok",
    [
        ("STANDARD", True),
        ("GLACIER", False),
        ("DEEP_ARCHIVE", False),
        ("STANDARD_IA", False),
        ("INTELLIGENT_TIERING", False),
        ("REDUCED_REDUNDANCY", False),
    ],
)
def test_a_storage_class_is_screened_against_what_is_stored(s3, bucket, value, ok):
    """`STANDARD` passes; every other class is `501`.

    A screen rather than a blanket refusal because one value is the
    truth: every listing reports `STANDARD` and that is where the object
    is. The rest name tiers with read-path semantics this format has not
    got — `GLACIER` is not directly readable at AWS and needs
    `RestoreObject`, which is `501` here — so storing the class and
    echoing it back would answer a claim a client acts on and this server
    cannot honour.
    """
    key = f"{PREFIX}class-{value}.bin"
    resp = raw_request(s3, "PUT", f"/{bucket}/{key}", body=b"body", headers={"x-amz-storage-class": value})
    if not ok:
        assert resp.status_code == 501, resp.content[:200]
        assert b"storage class" in resp.content
        return

    assert resp.status_code == 200, resp.content[:200]
    listed = s3.list_objects_v2(Bucket=bucket, Prefix=key)["Contents"][0]
    assert listed["StorageClass"] == "STANDARD", "agreeing with what the write said"


@pytest.mark.parametrize(
    "value,ok",
    [
        # `ObjectCannedACL` is the vocabulary a write is modeled against,
        # and all seven of its values belong here; the bucket's four are
        # a subset. Six store on an `OBJECT_WRITER` bucket.
        ("private", True),
        ("public-read", True),
        ("public-read-write", True),
        ("authenticated-read", True),
        ("bucket-owner-read", True),
        ("bucket-owner-full-control", True),
        # In AWS's object canned vocabulary and refused here anyway: both
        # name AWS-internal grantees this format has no code for, so a
        # 200 storing nothing would be the silent drop this file exists
        # to catch. `log-delivery-write` is AWS's bucket spelling, sent
        # here because a raw client can send it.
        ("aws-exec-read", False),
        ("log-delivery-write", False),
        # Case-sensitive, exactly as AWS spells the values.
        ("Private", False),
        ("public-ready", False),
    ],
)
def test_a_canned_acl_is_honored_or_refused_never_dropped(s3, bucket, value, ok):
    """Every canned value stores on an ACL-bearing bucket; a value
    outside the vocabulary is a `400`, never a silent drop.

    What the stored grants *are* is the ACL module's to assert; this file
    keeps only the never-silently-drop rule. The refusals assert the
    code, not just the status: a 400 under any other code would tell a
    client something else went wrong.
    """
    key = f"{PREFIX}acl-{value}.bin"
    resp = raw_request(s3, "PUT", f"/{bucket}/{key}", body=b"body", headers={"x-amz-acl": value})
    if not ok:
        assert resp.status_code == 400, resp.content[:200]
        assert b"InvalidArgument" in resp.content, resp.content[:200]
        with pytest.raises(Exception):
            s3.head_object(Bucket=bucket, Key=key)
        return

    assert resp.status_code == 200, resp.content[:200]
    assert s3.head_object(Bucket=bucket, Key=key)["ContentLength"] == 4
