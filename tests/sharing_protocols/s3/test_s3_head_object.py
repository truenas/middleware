"""HeadObject: the operation every client's hot path runs and nothing
else asserts.

botocore issues a `HEAD` before most transfers, and until this module
nothing checked that it answers the same thing `GET` does. A divergence
between the two would have been invisible: the listing cases read sizes
from the listing, and the range cases read the ETag from `HEAD` without
ever comparing it.
"""

import pytest
from s3_client import status_of

PREFIX = "head/"
BODY = b"0123456789"


@pytest.fixture(scope="module")
def obj(s3, bucket):
    key = f"{PREFIX}obj.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=BODY, ContentType="text/plain")
    return key


def test_a_head_and_a_get_agree_on_every_header(s3, bucket, obj):
    """The invariant the other cases rest on.

    Two code paths answer the same question and only one of them is
    exercised by the rest of the suite. If they ever disagree about a
    length or an ETag, every client that sizes a transfer from `HEAD` and
    then reads with `GET` is wrong by exactly that difference.
    """
    head = s3.head_object(Bucket=bucket, Key=obj)
    got = s3.get_object(Bucket=bucket, Key=obj)
    for field in ("ContentLength", "ETag", "ContentType", "LastModified"):
        assert head[field] == got[field], field
    assert got["Body"].read() == BODY
    assert head["ContentLength"] == len(BODY)


def test_a_head_of_an_absent_key_is_404(s3, bucket):
    """No `Error` document is parseable from a `HEAD` — there is no body
    by protocol — so the status is the whole answer."""
    with pytest.raises(Exception) as caught:
        s3.head_object(Bucket=bucket, Key=f"{PREFIX}never.bin")
    assert status_of(caught.value) == 404


def test_a_head_of_an_absent_bucket_is_404(s3):
    with pytest.raises(Exception) as caught:
        s3.head_object(Bucket="no-such-bucket-here", Key="k")
    assert status_of(caught.value) == 404


def test_a_directory_answers_head_only_by_its_slash(s3, bucket):
    """This server lists a directory as a 0-byte row, and that row is
    addressable — but by the name it has. `d/` is the key; `d` is not,
    and answering it would make two keys for one directory."""
    s3.put_object(Bucket=bucket, Key=f"{PREFIX}d/inside.txt", Body=b"x")

    assert s3.head_object(Bucket=bucket, Key=f"{PREFIX}d/")["ContentLength"] == 0
    with pytest.raises(Exception) as caught:
        s3.head_object(Bucket=bucket, Key=f"{PREFIX}d")
    assert status_of(caught.value) == 404


def test_a_head_under_a_file_prefix_is_refused_not_absent(s3, bucket):
    """`f/x` where `f` is an object cannot exist and cannot be created —
    the parent is not a directory.

    This server answers `400` rather than `404`, which is a divergence
    worth pinning rather than discovering: a client that treats it as
    "not yet" will retry for ever.
    """
    s3.put_object(Bucket=bucket, Key=f"{PREFIX}f", Body=b"f")
    with pytest.raises(Exception) as caught:
        s3.head_object(Bucket=bucket, Key=f"{PREFIX}f/x")
    assert status_of(caught.value) == 400


def test_a_conditional_head_answers_like_a_conditional_get(s3, bucket, obj):
    """The conditionals are asserted on `GET` next door; the point here
    is that `HEAD` runs the same evaluator, so a `304` means the same
    thing on both."""
    etag = s3.head_object(Bucket=bucket, Key=obj)["ETag"]

    for kwargs, want in (
        ({"IfNoneMatch": etag}, 304),
        ({"IfNoneMatch": "*"}, 304),
        ({"IfMatch": '"deadbeef"'}, 412),
    ):
        with pytest.raises(Exception) as caught:
            s3.head_object(Bucket=bucket, Key=obj, **kwargs)
        assert status_of(caught.value) == want, kwargs

    assert s3.head_object(Bucket=bucket, Key=obj, IfMatch=etag)["ContentLength"] == len(BODY)


def test_a_head_carries_the_user_metadata(s3, bucket):
    """What a client reads a `HEAD` for, other than the length."""
    key = f"{PREFIX}meta.bin"
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=b"x",
        Metadata={"origin": "probe", "run": "1"},
        ContentType="application/x-test",
    )
    head = s3.head_object(Bucket=bucket, Key=key)
    assert head["Metadata"] == {"origin": "probe", "run": "1"}
    assert head["ContentType"] == "application/x-test"
    assert head["Metadata"] == s3.get_object(Bucket=bucket, Key=key)["Metadata"]


def test_a_part_number_on_a_head_answers_206(s3, bucket, obj):
    """`?partNumber` on a whole object names its only part, and the
    answer is `206` with the whole length — which is how a client learns
    an object has no part structure worth reading round."""
    got = s3.head_object(Bucket=bucket, Key=obj, PartNumber=1)
    assert got["ResponseMetadata"]["HTTPStatusCode"] == 206
    assert got["ContentLength"] == len(BODY)


def test_a_head_range_affects_only_the_length(s3, bucket, obj):
    """The reference gives `Range` to HEAD with GET's semantics: *"If the
    Range is satisfiable, only the ContentLength is affected in the
    response"*, and an unsatisfiable one is the same 416."""
    got = s3.head_object(Bucket=bucket, Key=obj, Range="bytes=1-3")
    assert got["ResponseMetadata"]["HTTPStatusCode"] == 206
    assert got["ContentLength"] == 3
    assert got["ContentRange"] == f"bytes 1-3/{len(BODY)}"

    with pytest.raises(Exception) as caught:
        s3.head_object(Bucket=bucket, Key=obj, Range="bytes=9000-9999")
    assert status_of(caught.value) == 416
