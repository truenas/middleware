"""User metadata and the content headers: what an object stores beside
its bytes, and the two budgets it spends.

The budgets are separate and an object may spend both — 2048 bytes of
user metadata, and its own allowance for the six content headers. Each
boundary is asserted from the side that must be *accepted*, because a
cap applied one byte early refuses a conformant write and looks correct
to any case that only sent something obviously too large.
"""

import pytest
from s3_client import code_of, raw_request, status_of

PREFIX = "meta/"


def test_the_stored_type_and_pairs_come_back(s3, bucket):
    key = f"{PREFIX}round-trip.txt"
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=b"body",
        ContentType="application/x-test",
        Metadata={"color": "blue", "shape": "round"},
    )
    got = s3.get_object(Bucket=bucket, Key=key)
    assert got["ContentType"] == "application/x-test"
    assert got["Metadata"] == {"color": "blue", "shape": "round"}


def test_an_absent_content_type_reads_as_the_default(s3, bucket):
    """S3's default rather than an empty header, which a client would
    have to special-case."""
    key = f"{PREFIX}plain.txt"
    s3.put_object(Bucket=bucket, Key=key, Body=b"body")
    assert s3.get_object(Bucket=bucket, Key=key)["ContentType"] == "binary/octet-stream"


def test_the_content_headers_come_back_byte_for_byte(s3, bucket):
    """The five stored beside `Content-Type`.

    `Expires` is compared as the raw header: boto3 parses it into a
    datetime, and the value is stored verbatim and never reformatted,
    which is the whole point of keeping the client's bytes.
    """
    key = f"{PREFIX}headers.txt"
    sent = {
        "CacheControl": "max-age=31536000, immutable",
        "ContentDisposition": "attachment; filename*=UTF-8''caf%C3%A9.txt",
        "ContentEncoding": "gzip",
        "ContentLanguage": "en-GB, fr",
        "Expires": "Thu, 01 Jan 2026 00:00:00 GMT",
    }
    s3.put_object(Bucket=bucket, Key=key, Body=b"body", **sent)

    got = s3.get_object(Bucket=bucket, Key=key)
    got["Body"].read()
    for field, want in sent.items():
        if field == "Expires":
            raw = got["ResponseMetadata"]["HTTPHeaders"].get("expires")
            assert raw == want, f"Expires comes back verbatim: {raw}"
            continue
        assert got.get(field) == want, field

    head = s3.head_object(Bucket=bucket, Key=key)
    assert head.get("ContentDisposition") == sent["ContentDisposition"], "head carries them too"


def test_a_write_that_sent_no_content_headers_answers_none(s3, bucket):
    """Absent rather than empty: a client reading an empty
    `Content-Encoding` would try to decode bytes that were never
    encoded."""
    key = f"{PREFIX}bare.txt"
    s3.put_object(Bucket=bucket, Key=key, Body=b"body")
    got = s3.get_object(Bucket=bucket, Key=key)
    got["Body"].read()
    present = [f for f in ("CacheControl", "ContentEncoding", "ContentLanguage") if got.get(f) is not None]
    assert present == [], present


def test_an_overwrite_replaces_the_whole_metadata_set(s3, bucket):
    """The set travels with the bytes rather than beside them, so a write
    is a replacement and never a merge — a client that re-uploads an
    object to *drop* a pair has no other way to say so."""
    key = f"{PREFIX}replaced.txt"
    s3.put_object(Bucket=bucket, Key=key, Body=b"body", Metadata={"color": "blue"})
    assert s3.head_object(Bucket=bucket, Key=key)["Metadata"] == {"color": "blue"}

    s3.put_object(Bucket=bucket, Key=key, Body=b"body")
    assert s3.head_object(Bucket=bucket, Key=key)["Metadata"] == {}


def test_a_metadata_name_is_case_folded(s3, bucket):
    """`x-amz-meta-MiXeD` reads back as `mixed`.

    HTTP field names are case-insensitive, so two spellings of one name
    are one pair. Storing the client's casing would make the record
    depend on which client wrote it, and let a later `x-amz-meta-mixed`
    read as a second pair.
    """
    key = f"{PREFIX}case.txt"
    resp = raw_request(s3, "PUT", f"/{bucket}/{key}", body=b"body", headers={"x-amz-meta-MiXeD": "value"})
    assert resp.status_code == 200, resp.content[:200]
    assert s3.head_object(Bucket=bucket, Key=key)["Metadata"] == {"mixed": "value"}


def test_the_user_metadata_budget_is_its_own_two_kilobytes(s3, bucket):
    """2047 is stored and 2048 refuses.

    The boundary is the assertion: a cap applied at 2046 or at 4096
    passes any case that only sent something obviously too large. This is
    *not* the content-header budget below — an object may spend both.
    """
    at = s3.put_object(Bucket=bucket, Key=f"{PREFIX}at.txt", Body=b"x", Metadata={"k": "a" * 2047})
    assert at["ResponseMetadata"]["HTTPStatusCode"] == 200

    with pytest.raises(Exception) as caught:
        s3.put_object(Bucket=bucket, Key=f"{PREFIX}over.txt", Body=b"x", Metadata={"k": "a" * 2048})
    assert status_of(caught.value) == 400
    assert code_of(caught.value) == "MetadataTooLarge"


def test_the_content_header_budget_refuses_over_its_own_cap(s3, bucket):
    """The six share one allowance, and a set past it is refused rather
    than truncated."""
    with pytest.raises(Exception) as caught:
        s3.put_object(
            Bucket=bucket,
            Key=f"{PREFIX}toobig.txt",
            Body=b"body",
            ContentDisposition="attachment; filename=" + "a" * 3000,
        )
    assert code_of(caught.value) == "MetadataTooLarge"


def test_a_nameless_metadata_header_is_refused(s3, bucket):
    """A bare `x-amz-meta-` names no pair, and storing it would make the
    read echo a malformed header back at the next client."""
    resp = raw_request(s3, "PUT", f"/{bucket}/{PREFIX}nameless.txt", body=b"body", headers={"x-amz-meta-": "v"})
    assert resp.status_code == 400
    assert b"InvalidArgument" in resp.content


#: `Content-Encoding` sent, and what the object must answer. AWS strips
#: `aws-chunked` because it describes the *transfer* and not the stored
#: representation, so an object whose only encoding was the framing has
#: none at all — a client that saw one would try to gunzip bytes that
#: were never zipped.
AWS_CHUNKED = [
    ("gzip", "gzip"),
    ("deflate, gzip", "deflate,gzip"),
    ("gzip, aws-chunked", "gzip"),
    ("aws-chunked, gzip", "gzip"),
    ("aws-chunked", None),
    ("aws-chunked, aws-chunked", None),
]


@pytest.mark.parametrize("sent,stored", AWS_CHUNKED)
def test_aws_chunked_is_not_stored_as_a_content_encoding(s3, bucket, sent, stored):
    """The surviving tokens are rejoined without the sender's spacing,
    which is why `deflate, gzip` reads back as `deflate,gzip`: the stored
    value is a list of tokens rather than the client's bytes.

    Asserting the exact answer is what keeps a later change from quietly
    preserving `aws-chunked` in one of the six shapes.
    """
    key = f"{PREFIX}ce/{sent.replace(' ', '').replace(',', '_')}"
    s3.put_object(Bucket=bucket, Key=key, Body=b"body", ContentEncoding=sent)
    assert s3.head_object(Bucket=bucket, Key=key).get("ContentEncoding") == stored
