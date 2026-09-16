"""`x-amz-expected-bucket-owner`, and the twin a copy's source takes.

The caller states which account it believes owns the bucket. A request
that reached a different owner's must refuse — a misdirected write
landing in a stranger's bucket behind a `200` is the whole failure the
header exists to prevent, and the AWS model binds it on every
bucket-scoped operation this server implements.

**Both halves are asserted, and the matching one is the harder.** A
guard that refused every value would satisfy every mismatch case and be
indistinguishable from one that works; only the control says it admits.
Everything runs signed and authorized, so a refusal is attributable to
the expectation alone rather than to the grants.

The account is named by the canonical id `GetBucketAcl` reports in
`<Owner>` — the only bucket-owner identifier this server exposes — so
the cases read it back rather than deriving it.
"""

import pytest
from s3_client import code_of, status_of

KEY = "expected-owner/probe.bin"

#: The two operations whose refusal carries no body to read a `<Code>`
#: out of: HTTP gives a HEAD response no payload, so the status line is
#: the whole of the answer and asserting a code here would assert on
#: botocore's fallback rather than on anything this server sent.
BODILESS = {"HeadObject", "HeadBucket"}


@pytest.fixture(scope="module")
def owner(s3, bucket):
    """The bucket owner's canonical id, as a client learns it."""
    return s3.get_bucket_acl(Bucket=bucket)["Owner"]["ID"]


@pytest.fixture(scope="module")
def stranger(owner):
    """A *well-formed* canonical id for a different account.

    Mutating the last hex digit keeps the deployment's seed and type
    prefix intact and moves only the uid, so what is refused is the
    account and not the spelling — the shapes refused for their spelling
    are their own case below.
    """
    return owner[:-1] + ("0" if owner[-1] != "0" else "1")


@pytest.fixture(scope="module")
def seeded(s3, bucket):
    s3.put_object(Bucket=bucket, Key=KEY, Body=b"guarded")
    yield KEY
    s3.delete_object(Bucket=bucket, Key=KEY)


def calls(s3, bucket, key):
    """The operations both cases drive, as thunks taking the header."""
    return {
        "GetObject": lambda **kw: s3.get_object(Bucket=bucket, Key=key, **kw),
        "HeadObject": lambda **kw: s3.head_object(Bucket=bucket, Key=key, **kw),
        "PutObject": lambda **kw: s3.put_object(Bucket=bucket, Key=key + ".w", Body=b"x", **kw),
        "ListObjectsV2": lambda **kw: s3.list_objects_v2(Bucket=bucket, MaxKeys=1, **kw),
        "ListObjects": lambda **kw: s3.list_objects(Bucket=bucket, MaxKeys=1, **kw),
        "HeadBucket": lambda **kw: s3.head_bucket(Bucket=bucket, **kw),
        "GetBucketAcl": lambda **kw: s3.get_bucket_acl(Bucket=bucket, **kw),
        "DeleteObject": lambda **kw: s3.delete_object(Bucket=bucket, Key=key + ".w", **kw),
    }


def test_the_owners_own_id_changes_nothing(s3, bucket, owner, seeded):
    """The control, and half the point: a header naming the account that
    does own the bucket must leave every operation exactly as it was."""
    for name, call in calls(s3, bucket, seeded).items():
        call(ExpectedBucketOwner=owner)
        assert True, name


def test_another_accounts_id_refuses_every_operation(s3, bucket, stranger, seeded):
    """The caller is authorized for all of these and is refused anyway,
    which is what makes this the header's behaviour and not the grants':
    the identical calls in the case above succeed."""
    for name, call in calls(s3, bucket, seeded).items():
        with pytest.raises(Exception) as caught:
            call(ExpectedBucketOwner=stranger)
        assert status_of(caught.value) == 403, name
        if name not in BODILESS:
            assert code_of(caught.value) == "AccessDenied", name


@pytest.mark.parametrize(
    "label,value",
    [
        ("empty", ""),
        ("a bare uid", "65534"),
        ("not hex", "z" * 64),
        ("too short", "0" * 63),
        ("too long", "0" * 65),
    ],
)
def test_a_value_that_names_no_account_refuses(s3, bucket, seeded, label, value):
    """Fail-closed, and deliberately so.

    None of these is one of this deployment's canonical ids, so none can
    be the bucket's owner. Reading "unparseable" as "no expectation"
    would drop the guard in exactly the case a client got the account
    wrong, which is the case it exists for.
    """
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=seeded, ExpectedBucketOwner=value)
    assert status_of(caught.value) == 403, label
    assert code_of(caught.value) == "AccessDenied", label


def test_an_uppercase_respelling_is_not_the_same_id(s3, bucket, owner, seeded):
    """A canonical id is 64 *lowercase* hex, as the grantee grammar is.

    Kept apart from the case above because this one is the owner's actual
    id and differs only in case: a comparison folding case would pass it.
    """
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=seeded, ExpectedBucketOwner=owner.upper())
    assert status_of(caught.value) == 403
    assert code_of(caught.value) == "AccessDenied"


def test_the_source_twin_guards_the_bucket_a_copy_reads(s3, bucket, owner, stranger, seeded):
    """`x-amz-source-expected-bucket-owner`, the read end of the guard.

    Honouring the destination's expectation and dropping the source's
    would leave the hole open on exactly the operation that reads one
    bucket and writes another.
    """
    source = {"Bucket": bucket, "Key": seeded}
    dest = "expected-owner/copied.bin"

    s3.copy_object(
        Bucket=bucket,
        Key=dest,
        CopySource=source,
        ExpectedBucketOwner=owner,
        ExpectedSourceBucketOwner=owner,
    )
    s3.delete_object(Bucket=bucket, Key=dest)

    for label, kwargs in (
        ("the source's", {"ExpectedSourceBucketOwner": stranger}),
        ("the destination's", {"ExpectedBucketOwner": stranger}),
    ):
        with pytest.raises(Exception) as caught:
            s3.copy_object(Bucket=bucket, Key=dest, CopySource=source, **kwargs)
        assert status_of(caught.value) == 403, label
        assert code_of(caught.value) == "AccessDenied", label
