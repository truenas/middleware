"""GetObject: windows over an object, and the four conditional headers.

The range cases are the boundaries — past EOF, a suffix, an empty
object, an unsatisfiable start — and the conditional ones are the
precedence rule between a validator and the date beside it.

**Why the precedence is asserted in both directions.** Each pair is
decided by its own validator and the date is subordinate to it: an
`If-None-Match` that *passes* must not then be turned into a 304 by an
`If-Modified-Since` that would have failed on its own. A server that
consulted the date anyway answers a cached 304 for a representation the
client does not have, and only the passing direction sees it.
"""

import datetime

import pytest
from s3_client import code_of, drain, payload, status_of

PREFIX = "get/"
BODY = b"".join(bytes([i % 256]) for i in range(1024))
FUTURE = datetime.datetime(2100, 1, 1, tzinfo=datetime.timezone.utc)
PAST = datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc)


@pytest.fixture(scope="module")
def obj(s3, bucket):
    """One 1 KiB object with position-dependent content."""
    drain(s3, bucket, PREFIX)
    key = f"{PREFIX}body.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=BODY)
    yield key
    drain(s3, bucket, PREFIX)


# ── ranges ───────────────────────────────────────────────────────────


def test_a_range_returns_206_and_the_named_bytes(s3, bucket, obj):
    got = s3.get_object(Bucket=bucket, Key=obj, Range="bytes=4-7")
    assert got["ResponseMetadata"]["HTTPStatusCode"] == 206
    assert got["Body"].read() == BODY[4:8]
    assert got["ContentRange"] == f"bytes 4-7/{len(BODY)}"
    assert got["ContentLength"] == 4


def test_a_range_reaching_past_the_end_is_clamped(s3, bucket, obj):
    """A range whose start is inside the object is satisfiable however
    far its end reaches; the answer is the tail and `Content-Range` names
    the real end. Refusing it would break every client that asks for a
    fixed window at an unknown size."""
    got = s3.get_object(Bucket=bucket, Key=obj, Range=f"bytes=512-{len(BODY) + 5000}")
    assert got["ResponseMetadata"]["HTTPStatusCode"] == 206
    assert got["Body"].read() == BODY[512:]
    assert got["ContentRange"] == f"bytes 512-{len(BODY) - 1}/{len(BODY)}"


def test_a_suffix_range_returns_the_tail(s3, bucket, obj):
    """`bytes=-N` is the last N bytes, not a range from N — the grammar
    an implementation most often reads as an inverted pair."""
    got = s3.get_object(Bucket=bucket, Key=obj, Range="bytes=-10")
    assert got["Body"].read() == BODY[-10:]
    end = len(BODY) - 1
    assert got["ContentRange"] == f"bytes {end - 9}-{end}/{len(BODY)}"


def test_an_open_ended_range_returns_from_the_offset(s3, bucket, obj):
    got = s3.get_object(Bucket=bucket, Key=obj, Range="bytes=1000-")
    assert got["Body"].read() == BODY[1000:]
    assert got["ContentRange"] == f"bytes 1000-{len(BODY) - 1}/{len(BODY)}"


def test_a_range_starting_past_the_end_is_416(s3, bucket, obj):
    """The one range answer that is an error rather than a clamp."""
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=obj, Range=f"bytes={len(BODY)}-{len(BODY) + 10}")
    assert status_of(caught.value) == 416
    assert code_of(caught.value) == "InvalidRange"


@pytest.mark.parametrize("rng", ["bytes=0-0", "bytes=0-", "bytes=-1"])
def test_every_range_on_an_empty_object_is_416(s3, bucket, rng):
    """A zero-length object satisfies no range at all, `bytes=0-0`
    included: there is no byte zero."""
    key = f"{PREFIX}empty.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"")
    try:
        with pytest.raises(Exception) as caught:
            s3.get_object(Bucket=bucket, Key=key, Range=rng)
        assert status_of(caught.value) == 416, rng
    finally:
        s3.delete_object(Bucket=bucket, Key=key)


@pytest.mark.parametrize("rng", ["bytes=abc-def", "items=0-9", "bytes=9-0", "bytes=", "0-9"])
def test_a_malformed_range_is_ignored_not_refused(s3, bucket, obj, rng):
    """RFC 9110 §14.2: an unsatisfiable *syntax* is not an error, it is
    an absent range.

    The distinction matters because the two answers are
    200-with-everything and 416-with-nothing, and a client that asked for
    a window it mistyped would rather have the object.
    """
    got = s3.get_object(Bucket=bucket, Key=obj, Range=rng)
    assert got["ResponseMetadata"]["HTTPStatusCode"] == 200, rng
    assert "ContentRange" not in got, rng
    assert got["Body"].read() == BODY, rng


# ── conditional reads ────────────────────────────────────────────────


def test_if_match_on_the_stored_etag_serves(s3, bucket, obj):
    etag = s3.head_object(Bucket=bucket, Key=obj)["ETag"]
    assert s3.get_object(Bucket=bucket, Key=obj, IfMatch=etag)["Body"].read() == BODY


def test_if_match_on_another_etag_is_412(s3, bucket, obj):
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=obj, IfMatch='"deadbeef"')
    assert status_of(caught.value) == 412
    assert code_of(caught.value) == "PreconditionFailed"


def test_if_none_match_on_the_stored_etag_is_304(s3, bucket, obj):
    """304 and not 412: a read whose condition says "only if it changed"
    is answered with "it did not", which carries no body and is not an
    error."""
    etag = s3.head_object(Bucket=bucket, Key=obj)["ETag"]
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=obj, IfNoneMatch=etag)
    assert status_of(caught.value) == 304


def test_if_none_match_on_another_etag_serves(s3, bucket, obj):
    assert s3.get_object(Bucket=bucket, Key=obj, IfNoneMatch='"deadbeef"')["Body"].read() == BODY


def test_a_star_if_none_match_is_304_for_an_object_that_exists(s3, bucket, obj):
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=obj, IfNoneMatch="*")
    assert status_of(caught.value) == 304


def test_a_passing_if_none_match_retires_the_date_beside_it(s3, bucket, obj):
    """A precedence bug this server once had, kept as a test.

    The `If-None-Match` passes — the ETag does not match, so the read
    proceeds — and the `If-Modified-Since` beside it would have failed on
    its own. The read must still serve.
    """
    got = s3.get_object(Bucket=bucket, Key=obj, IfNoneMatch='"deadbeef"', IfModifiedSince=FUTURE)
    assert got["ResponseMetadata"]["HTTPStatusCode"] == 200
    assert got["Body"].read() == BODY


def test_a_failing_if_match_beats_an_unmodified_since_that_would_pass(s3, bucket, obj):
    """The other direction of the same rule: `If-Match` decides, and a
    satisfied `If-Unmodified-Since` beside it does not rescue a read
    whose ETag was wrong."""
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=obj, IfMatch='"deadbeef"', IfUnmodifiedSince=FUTURE)
    assert status_of(caught.value) == 412


def test_if_modified_since_before_the_write_serves(s3, bucket, obj):
    assert s3.get_object(Bucket=bucket, Key=obj, IfModifiedSince=PAST)["Body"].read() == BODY


def test_if_modified_since_after_the_write_is_304(s3, bucket, obj):
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=obj, IfModifiedSince=FUTURE)
    assert status_of(caught.value) == 304


def test_if_unmodified_since_before_the_write_is_412(s3, bucket, obj):
    """412 and not 304: the condition is a precondition on a write-like
    read, and its failure is an error rather than a cache answer."""
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=obj, IfUnmodifiedSince=PAST)
    assert status_of(caught.value) == 412
    assert code_of(caught.value) == "PreconditionFailed"


def test_if_unmodified_since_after_the_write_serves(s3, bucket, obj):
    assert s3.get_object(Bucket=bucket, Key=obj, IfUnmodifiedSince=FUTURE)["Body"].read() == BODY


def test_a_conditional_read_of_an_absent_key_is_404_not_412(s3, bucket):
    """Existence is decided before any precondition.

    A client polling a key it expects to appear sends `If-None-Match: *`
    and must be able to tell "not there yet" from "there and unchanged".
    """
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=f"{PREFIX}never.bin", IfMatch='"x"')
    assert status_of(caught.value) == 404
    assert code_of(caught.value) == "NoSuchKey"


def test_a_range_and_a_failed_condition_answer_the_condition(s3, bucket, obj):
    """A server that applied the range first would answer 206 with bytes
    the condition forbade."""
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=obj, Range="bytes=0-9", IfMatch='"deadbeef"')
    assert status_of(caught.value) == 412


# ── the response-header overrides ────────────────────────────────────


def test_the_response_overrides_replace_the_content_headers(s3, bucket):
    """The six `response-*` parameters, on both read verbs.

    What they are worth is that a presigned download URL can name the
    filename a browser saves under: the parameter rides the canonical
    query, so it is inside the signature by construction.
    """
    key = f"{PREFIX}override.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"body", ContentType="text/plain")
    overrides = {
        "ResponseContentType": "foo/bar",
        "ResponseContentDisposition": 'attachment; filename="r.pdf"',
        "ResponseContentEncoding": "gzip",
        "ResponseContentLanguage": "esperanto",
        "ResponseCacheControl": "no-cache",
    }
    want = {
        "content-type": "foo/bar",
        "content-disposition": 'attachment; filename="r.pdf"',
        "content-encoding": "gzip",
        "content-language": "esperanto",
        "cache-control": "no-cache",
    }
    for verb in ("get_object", "head_object"):
        got = getattr(s3, verb)(Bucket=bucket, Key=key, **overrides)
        headers = got["ResponseMetadata"]["HTTPHeaders"]
        for name, value in want.items():
            assert headers.get(name) == value, f"{verb} {name}"
        if verb == "get_object":
            assert got["Body"].read() == b"body"

    # The one the stored value answers, unasked-for.
    plain = s3.get_object(Bucket=bucket, Key=key)
    assert plain["ResponseMetadata"]["HTTPHeaders"]["content-type"] == "text/plain"


@pytest.mark.parametrize("verb", ["get_object", "head_object"])
def test_a_read_of_an_absent_key_is_404(s3, bucket, verb):
    with pytest.raises(Exception) as caught:
        getattr(s3, verb)(Bucket=bucket, Key=f"{PREFIX}nothing/here.txt")
    assert status_of(caught.value) == 404


def test_a_ranged_read_carries_no_whole_object_checksum(s3, bucket):
    """A checksum covers the whole object, so a window over part of it
    must not carry one — an SDK verifies the header against the bytes it
    received and would fail the read."""
    key = f"{PREFIX}summed.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=payload(4096))
    whole = s3.get_object(Bucket=bucket, Key=key, ChecksumMode="ENABLED")
    whole["Body"].read()
    assert whole.get("ChecksumCRC32") is not None, "the write stored one"

    ranged = s3.get_object(Bucket=bucket, Key=key, Range="bytes=0-99", ChecksumMode="ENABLED")
    ranged["Body"].read()
    assert ranged.get("ChecksumCRC32") is None
