"""Keys a POSIX tree cannot hold, and what each defect is answered with.

The bucket is a ZFS dataset, so a key is a path and some keys have no
representation: a component past `NAME_MAX`, a `.` or `..` element, an
empty one. Each gets a distinct answer, and the table is a **write's**:
a read takes every one of them as absence, because for a reader they are
one fact — nothing this server can hold sits under that name.

Both directions are asserted, because the two drifting into each other
is the failure that matters. A write answered `NoSuchKey` tells a client
to retry a key this tree can never hold, and it will retry for ever.
"""

import pytest
from s3_client import code_of, status_of

PREFIX = "shape/"

# One byte past `NAME_MAX`, which is the row the boundary sits on.
AT_LIMIT = "n" * 255
OVERLONG = "n" * 256


def test_a_component_at_the_ceiling_is_stored(s3, bucket):
    """255 bytes is a name; 256 is not. Asserted from the side that must
    work, so a stricter screen cannot pass unnoticed."""
    key = f"{PREFIX}{AT_LIMIT}"
    s3.put_object(Bucket=bucket, Key=key, Body=b"z")
    assert s3.get_object(Bucket=bucket, Key=key)["Body"].read() == b"z"


@pytest.mark.parametrize(
    "key",
    [OVERLONG, f"p/{OVERLONG}", f"{OVERLONG}/leaf"],
    ids=["alone", "as a leaf", "as a parent"],
)
def test_a_write_of_an_overlong_component_names_the_row(s3, bucket, key):
    """`KeyTooLongError`, not `NoSuchKey`.

    The client asked for bytes to be stored, and absence answers a
    question it did not ask. The position is parametrized because a
    screen that only measured the last component would pass two of these.
    """
    with pytest.raises(Exception) as caught:
        s3.put_object(Bucket=bucket, Key=key, Body=b"z")
    assert status_of(caught.value) == 400, key
    assert code_of(caught.value) == "KeyTooLongError", key


@pytest.mark.parametrize("key", ["a/./b", "a/../b", "a//b"])
def test_a_write_of_a_shape_the_tree_cannot_hold_names_the_row(s3, bucket, key):
    """The `InvalidArgument` half of the same table: a path element that
    resolves to somewhere else, or to nothing."""
    with pytest.raises(Exception) as caught:
        s3.put_object(Bucket=bucket, Key=key, Body=b"z")
    assert status_of(caught.value) == 400, key
    assert code_of(caught.value) == "InvalidArgument", key


@pytest.mark.parametrize("key", [OVERLONG, "a/./b", "a/../b", "a//b"])
def test_a_read_of_the_same_shapes_is_absence(s3, bucket, key):
    """`NoSuchKey` for every one of them.

    Naming the defect on a read would only say how the tree is built, and
    a reader cannot act on it either way.
    """
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=key)
    assert status_of(caught.value) == 404, key
    assert code_of(caught.value) == "NoSuchKey", key


def test_a_delete_of_an_overlong_component_is_idempotent(s3, bucket):
    """Destruction is idempotent and what cannot exist is already gone,
    so this is neither of the answers above."""
    s3.delete_object(Bucket=bucket, Key=OVERLONG)


def test_a_write_over_a_directory_is_refused(s3, bucket):
    """A key that is currently a directory cannot become an object
    without destroying everything under it, so the write is refused
    rather than silently doing one or the other."""
    s3.put_object(Bucket=bucket, Key=f"{PREFIX}dir/inside.txt", Body=b"x")
    with pytest.raises(Exception) as caught:
        s3.put_object(Bucket=bucket, Key=f"{PREFIX}dir", Body=b"z")
    assert status_of(caught.value) == 400
    assert code_of(caught.value) == "InvalidRequest"


def test_a_write_under_a_file_prefix_is_refused(s3, bucket):
    """The mirror of the case above: `f/x` where `f` is an object.

    This is what a client actually hits, by syncing a tree where a name
    changed from a file to a directory.
    """
    s3.put_object(Bucket=bucket, Key=f"{PREFIX}f", Body=b"f")
    with pytest.raises(Exception) as caught:
        s3.put_object(Bucket=bucket, Key=f"{PREFIX}f/nested", Body=b"z")
    assert status_of(caught.value) == 400
    assert code_of(caught.value) == "InvalidRequest"


def test_a_directory_key_takes_no_body(s3, bucket):
    """A key ending in `/` is a directory here and stores nothing, so a
    body is a request this server cannot carry out — refused rather than
    accepted and dropped, which would lose data silently."""
    with pytest.raises(Exception) as caught:
        s3.put_object(Bucket=bucket, Key=f"{PREFIX}withbody/", Body=b"abc")
    assert status_of(caught.value) == 400
    assert code_of(caught.value) == "InvalidRequest"


def test_an_empty_directory_key_is_the_folder_marker(s3, bucket):
    """The shape every console and sync tool actually sends: the same key
    with no body, which is what "Create folder" is."""
    got = s3.put_object(Bucket=bucket, Key=f"{PREFIX}folder/", Body=b"")
    assert got["ResponseMetadata"]["HTTPStatusCode"] == 200
    assert s3.head_object(Bucket=bucket, Key=f"{PREFIX}folder/")["ContentLength"] == 0
