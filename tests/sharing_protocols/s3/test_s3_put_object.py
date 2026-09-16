"""PutObject: the write path, its bounds and its conditionals.

The sizes are the point of the round trip. `SIZES` straddles the
daemon's buffered cap in both directions, so one parametrized case
covers the buffered write, the streamed write and the boundary between
them — which are three code paths answering one API.
"""

import hashlib

import pytest
from s3_client import CHUNK, SIZES, code_of, digest, payload, status_of

PREFIX = "put/"


@pytest.mark.parametrize("size", SIZES, ids=[str(n) for n in SIZES])
def test_a_write_round_trips_byte_for_byte(s3, bucket, size):
    """Every size, byte for byte, with the ETag agreeing across calls.

    The ETag assertion is the prediction: the record the write stamped is
    the one this read believed. A change cookie that moved under the
    object would answer a *derived* tag instead, over the same bytes, and
    nothing about the body would say so.
    """
    key = f"{PREFIX}sized-{size}.bin"
    body = payload(size)
    etag = s3.put_object(Bucket=bucket, Key=key, Body=body)["ETag"]

    got = s3.get_object(Bucket=bucket, Key=key)
    back = got["Body"].read()
    assert len(back) == size
    assert digest(back) == digest(body)
    assert got["ContentLength"] == size
    assert got["ETag"] == etag, "the read believed the record the write stamped"

    head = s3.head_object(Bucket=bucket, Key=key)
    assert (head["ETag"], head["ContentLength"]) == (etag, size)

    # A read must not move what it reports.
    again = s3.get_object(Bucket=bucket, Key=key)
    assert again["ETag"] == etag
    again["Body"].read()


def test_a_write_past_the_buffered_cap_streams(s3, bucket):
    """A single PUT larger than the daemon will buffer.

    48 MiB is past any buffered cap, so this is the streamed entity path
    and nothing else. Compared by digest rather than by a held copy: the
    object is bigger than a test should keep around twice.
    """
    size = 48 * CHUNK
    key = f"{PREFIX}streamed.bin"
    body = payload(size)
    want = digest(body)
    answered = s3.put_object(Bucket=bucket, Key=key, Body=body)
    del body
    assert answered["ResponseMetadata"]["HTTPStatusCode"] == 200

    raw = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    assert len(raw) == size
    assert digest(raw) == want
    s3.delete_object(Bucket=bucket, Key=key)


def test_an_overwrite_replaces_the_name_and_mints_a_new_tag(s3, bucket):
    key = f"{PREFIX}twice.bin"
    first = s3.put_object(Bucket=bucket, Key=key, Body=b"first")["ETag"]
    second = s3.put_object(Bucket=bucket, Key=key, Body=b"second")["ETag"]
    assert first != second

    got = s3.get_object(Bucket=bucket, Key=key)
    assert got["Body"].read() == b"second"
    assert got["ETag"] == second


def test_a_create_only_write_is_decided_by_the_rename(s3, bucket):
    """`If-None-Match: *` asks whether the *name* is free.

    The delete first is not tidying: a create-only write needs its name
    free, and a delete is how a name comes free on every run alike —
    idempotent, so a fresh tree and a reused one answer the same 204
    before the create.
    """
    key = f"{PREFIX}once.bin"
    s3.delete_object(Bucket=bucket, Key=key)
    s3.put_object(Bucket=bucket, Key=key, Body=b"first", IfNoneMatch="*")

    with pytest.raises(Exception) as caught:
        s3.put_object(Bucket=bucket, Key=key, Body=b"second", IfNoneMatch="*")
    assert status_of(caught.value) == 412
    assert code_of(caught.value) == "PreconditionFailed"
    assert s3.get_object(Bucket=bucket, Key=key)["Body"].read() == b"first"


def test_a_conditional_replace_is_a_compare_and_swap(s3, bucket):
    """`If-Match`: the swap the publish decides under the key's claim,
    against the ETag a read would answer."""
    key = f"{PREFIX}cas.bin"
    first = s3.put_object(Bucket=bucket, Key=key, Body=b"first")["ETag"]

    with pytest.raises(Exception) as caught:
        s3.put_object(Bucket=bucket, Key=key, Body=b"never", IfMatch='"mismatch"')
    assert status_of(caught.value) == 412
    assert code_of(caught.value) == "PreconditionFailed"

    second = s3.put_object(Bucket=bucket, Key=key, Body=b"second", IfMatch=first)["ETag"]
    assert second != first

    # The superseded tag no longer matches.
    with pytest.raises(Exception) as caught:
        s3.put_object(Bucket=bucket, Key=key, Body=b"never", IfMatch=first)
    assert status_of(caught.value) == 412

    got = s3.get_object(Bucket=bucket, Key=key)
    assert (got["Body"].read(), got["ETag"]) == (b"second", second)


def test_if_match_star_on_a_missing_key_is_refused(s3, bucket):
    """A missing key matches nothing, `*` included.

    AWS answers 404 here and this server answers 412, which is a recorded
    divergence: one error for one question — the condition was not met.
    """
    key = f"{PREFIX}absent.bin"
    s3.delete_object(Bucket=bucket, Key=key)
    with pytest.raises(Exception) as caught:
        s3.put_object(Bucket=bucket, Key=key, Body=b"never", IfMatch="*")
    assert status_of(caught.value) == 412


def test_a_content_md5_binds_the_body(s3, bucket):
    """`BadDigest` is the wrong digest; `InvalidDigest` is not a digest.

    The separation is the useful part: the first is corruption in transit
    that a retry may well fix, and the second is a client bug no retry
    fixes. A four-byte base64 value is well-formed base64 and not an MD5,
    which is why it lands on the second.
    """
    import base64

    key = f"{PREFIX}digest.bin"
    body = b"x"
    right = base64.b64encode(hashlib.md5(body).digest()).decode()
    other = base64.b64encode(hashlib.md5(b"y").digest()).decode()

    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentMD5=right)

    with pytest.raises(Exception) as caught:
        s3.put_object(Bucket=bucket, Key=key, Body=body, ContentMD5=other)
    assert (status_of(caught.value), code_of(caught.value)) == (400, "BadDigest")

    with pytest.raises(Exception) as caught:
        s3.put_object(Bucket=bucket, Key=key, Body=body, ContentMD5="lVk/nw==")
    assert (status_of(caught.value), code_of(caught.value)) == (400, "InvalidDigest")
