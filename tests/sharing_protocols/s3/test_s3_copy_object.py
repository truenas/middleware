"""CopyObject: what it carries, what it mints, and what gates it.

A copy is the operation a client uses to rename an object, to edit its
metadata in place, and to duplicate it — three different intentions
reaching one API through the two directives. Each directive is proved
against the same source, because a working `REPLACE` and one that
silently carried the source's values anyway are indistinguishable from
a case that only sent `REPLACE`.
"""

import datetime

import pytest
from s3_client import code_of, status_of

PREFIX = "copy/"


@pytest.fixture
def source(s3, bucket):
    """One object carrying every field a copy might or might not move."""
    key = f"{PREFIX}source.bin"
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=b"source bytes",
        ContentType="audio/ogg",
        Metadata={"k1": "v1", "k2": "v2"},
    )
    s3.put_object_tagging(Bucket=bucket, Key=key, Tagging={"TagSet": [{"Key": "tier", "Value": "cold"}]})
    return key


def test_a_copy_carries_the_bytes_and_mints_its_own_etag(s3, bucket, source):
    """The destination is a new inode, so its identity is minted fresh
    for it — the bytes are the same and the ETag is not."""
    src_etag = s3.head_object(Bucket=bucket, Key=source)["ETag"]
    dst = f"{PREFIX}clone.bin"
    s3.copy_object(Bucket=bucket, Key=dst, CopySource={"Bucket": bucket, "Key": source})

    got = s3.get_object(Bucket=bucket, Key=dst)
    assert got["Body"].read() == b"source bytes"
    assert got["ContentType"] == "audio/ogg"
    assert got["ETag"] != src_etag, "a copy mints its own ETag"


def test_a_copy_carries_the_sources_metadata_and_type(s3, bucket, source):
    """`COPY` is the default, and it moves both.

    A client that copies to rename expects the copy to *be* the object; a
    content type silently reset to the default would make every browser
    download the copy as a file rather than play it.
    """
    dst = f"{PREFIX}carried.bin"
    s3.copy_object(Bucket=bucket, Key=dst, CopySource={"Bucket": bucket, "Key": source})
    got = s3.get_object(Bucket=bucket, Key=dst)
    assert got["ContentType"] == "audio/ogg"
    assert got["Metadata"] == {"k1": "v1", "k2": "v2"}
    assert got["Body"].read() == b"source bytes"


def test_replace_takes_the_requests_metadata_and_type(s3, bucket, source):
    dst = f"{PREFIX}replaced.bin"
    s3.copy_object(
        Bucket=bucket,
        Key=dst,
        CopySource={"Bucket": bucket, "Key": source},
        MetadataDirective="REPLACE",
        Metadata={"k3": "v3"},
        ContentType="audio/mpeg",
    )
    got = s3.get_object(Bucket=bucket, Key=dst)
    assert got["ContentType"] == "audio/mpeg"
    assert got["Metadata"] == {"k3": "v3"}
    assert got["Body"].read() == b"source bytes"


def test_replace_with_nothing_clears_the_set(s3, bucket, source):
    """A directive that quietly fell back to `COPY` when the request
    carried no pairs would pass every case that sent some, and would
    leave a client unable to *strip* metadata at all."""
    dst = f"{PREFIX}cleared.bin"
    s3.copy_object(
        Bucket=bucket,
        Key=dst,
        CopySource={"Bucket": bucket, "Key": source},
        MetadataDirective="REPLACE",
    )
    got = s3.get_object(Bucket=bucket, Key=dst)
    assert got["Metadata"] == {}
    assert got["ContentType"] == "binary/octet-stream"


def test_the_tagging_directive_carries_or_clears(s3, bucket, source):
    """The tag set's own `COPY`/`REPLACE`, independent of the metadata
    one.

    The pairing matters: a copy that replaced metadata would otherwise
    have to choose between dropping tags a client meant to keep and
    keeping tags a client meant to drop. `REPLACE` with no `x-amz-tagging`
    beside it names the empty set.
    """
    kept = f"{PREFIX}tags-kept.bin"
    s3.copy_object(Bucket=bucket, Key=kept, CopySource={"Bucket": bucket, "Key": source})
    assert s3.get_object_tagging(Bucket=bucket, Key=kept)["TagSet"] == [{"Key": "tier", "Value": "cold"}]

    dropped = f"{PREFIX}tags-dropped.bin"
    s3.copy_object(
        Bucket=bucket,
        Key=dropped,
        CopySource={"Bucket": bucket, "Key": source},
        TaggingDirective="REPLACE",
    )
    assert s3.get_object_tagging(Bucket=bucket, Key=dropped)["TagSet"] == []


def test_a_self_copy_that_changes_nothing_is_refused(s3, bucket, source):
    """The destination is a new inode, so the ETag would move though the
    bytes did not — which is a change a client did not ask for."""
    with pytest.raises(Exception) as caught:
        s3.copy_object(Bucket=bucket, Key=source, CopySource={"Bucket": bucket, "Key": source})
    assert status_of(caught.value) == 400
    assert code_of(caught.value) == "InvalidRequest"


def test_a_self_copy_that_replaces_metadata_rewrites_it(s3, bucket, source):
    """The one legal self-copy, and the thing it is for: it is the only
    way S3 gives a client to edit metadata in place."""
    s3.copy_object(
        Bucket=bucket,
        Key=source,
        CopySource={"Bucket": bucket, "Key": source},
        MetadataDirective="REPLACE",
        Metadata={"edited": "yes"},
    )
    got = s3.get_object(Bucket=bucket, Key=source)
    assert got["Metadata"] == {"edited": "yes"}
    assert got["Body"].read() == b"source bytes"


def test_a_copy_of_a_missing_key_refuses_and_the_connection_survives(s3, bucket, source):
    with pytest.raises(Exception) as caught:
        s3.copy_object(
            Bucket=bucket,
            Key=f"{PREFIX}ghost-dst.bin",
            CopySource={"Bucket": bucket, "Key": f"{PREFIX}ghost.bin"},
        )
    assert status_of(caught.value) == 404
    assert code_of(caught.value) == "NoSuchKey"
    assert s3.get_object(Bucket=bucket, Key=source)["Body"].read() == b"source bytes"


def test_a_zero_length_object_copies(s3, bucket):
    """An empty source is a copy of nothing, not a copy of nothing to do.

    A copy path that reads a length and then a body will read zero and
    can be written to skip the write entirely, leaving the destination
    absent behind a 200.
    """
    s3.put_object(Bucket=bucket, Key=f"{PREFIX}empty.bin", Body=b"")
    s3.copy_object(
        Bucket=bucket,
        Key=f"{PREFIX}empty-copy.bin",
        CopySource={"Bucket": bucket, "Key": f"{PREFIX}empty.bin"},
    )
    assert s3.head_object(Bucket=bucket, Key=f"{PREFIX}empty-copy.bin")["ContentLength"] == 0


def test_the_copy_source_conditions_combine_by_validator(s3, bucket, source):
    """Not "each supplied pair must pass": a satisfied validator retires
    the date beside it, in both directions.

    S3 states this operation's case outright —
    `x-amz-copy-source-if-match` true beside
    `x-amz-copy-source-if-unmodified-since` false is 200 and the copy.
    Every failure is 412; a copy has no cached representation to reuse,
    so there is no 304 to answer.
    """
    etag = s3.head_object(Bucket=bucket, Key=source)["ETag"]
    other = '"00000000-0000-4000-8000-000000000000"'
    long_ago = datetime.datetime(1970, 1, 1, 0, 0, 1, tzinfo=datetime.timezone.utc)
    far_off = datetime.datetime(2100, 1, 1, tzinfo=datetime.timezone.utc)
    src = {"Bucket": bucket, "Key": source}

    def copy(name, **kwargs):
        return s3.copy_object(Bucket=bucket, Key=f"{PREFIX}cond-{name}.bin", CopySource=src, **kwargs)

    def refused(name, **kwargs):
        with pytest.raises(Exception) as caught:
            copy(name, **kwargs)
        assert status_of(caught.value) == 412, name

    copy("m-ok", CopySourceIfMatch=etag)
    refused("m-no", CopySourceIfMatch=other)
    copy("nm-ok", CopySourceIfNoneMatch=other)
    refused("nm-no", CopySourceIfNoneMatch=etag)
    refused("um-no", CopySourceIfUnmodifiedSince=long_ago)
    refused("ms-no", CopySourceIfModifiedSince=far_off)

    # A validator that decides, paired with a date that would have
    # decided the other way on its own.
    copy("m-beats-um", CopySourceIfMatch=etag, CopySourceIfUnmodifiedSince=long_ago)
    copy("nm-beats-ms", CopySourceIfNoneMatch=other, CopySourceIfModifiedSince=far_off)


def test_a_copy_destination_takes_the_write_conditionals(s3, bucket, source):
    """The destination's conditionals are the publish's, so a copy is
    gated by the same chain a PUT is — and `If-None-Match` here is the
    destination's, never the source's."""
    dst = f"{PREFIX}gated.bin"
    dest_etag = s3.put_object(Bucket=bucket, Key=dst, Body=b"first")["ETag"]
    src = {"Bucket": bucket, "Key": source}

    with pytest.raises(Exception) as caught:
        s3.copy_object(Bucket=bucket, Key=dst, CopySource=src, IfNoneMatch=dest_etag)
    assert status_of(caught.value) == 412
    assert code_of(caught.value) == "PreconditionFailed"
    assert s3.get_object(Bucket=bucket, Key=dst)["Body"].read() == b"first"

    s3.copy_object(Bucket=bucket, Key=dst, CopySource=src, IfNoneMatch='"other"')
    assert s3.get_object(Bucket=bucket, Key=dst)["Body"].read() == b"source bytes"
