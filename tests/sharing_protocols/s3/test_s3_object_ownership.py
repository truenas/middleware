"""Object ownership over the wire: which account a write is recorded as.

`object_ownership` is one of the two axes a bucket carries, and it is
the one that decides which uid the kernel sees for a publish and whether
the bucket has an S3 ACL surface at all. Every value is proved here
against a bucket middleware provisioned for it, because the answer is
per bucket and a single row cannot show two of them.

The `OBJECT_WRITER` and `BUCKET_OWNER_ENFORCED` cases moved here from
``tests/api2/test_s3_bucket.py``: they were always protocol tests — two
signed clients, real objects, and the uid on disk — and what they prove
is the wiring between the value middleware stored and the personality
the daemon publishes under. The `BUCKET_OWNER_PREFERRED` half is the
conditional table AWS documents, driven against the bucket the session
owns for it.
"""

from middlewared.test.integration.assets.s3 import s3_account, s3_bucket, s3_service, user_grant
from middlewared.test.integration.utils import call, pool, ssh
import pytest
from s3_client import client_for, code_of

DATASET = f"{pool}/s3proto-ownership"
BUCKET = "s3proto-ownership"


@pytest.fixture(scope="module")
def writers():
    """Two accounts with keys, and a third holding no grant at all.

    Two granted writers rather than one: under `OBJECT_WRITER` every
    publish lands under the requester's own uid, so the second one
    writing into a prefix the first created — and over the first's
    object — is what proves the `S3` permissions model ignores the modes
    those writes leave behind. The stranger is the control: the value
    moves which uid the kernel sees and never who is authorized.
    """
    with (
        s3_account("s3protow1") as one,
        s3_account("s3protow2") as two,
        s3_account("s3protow3") as stranger,
    ):
        yield one, two, stranger


@pytest.fixture
def owned(writers):
    """A bucket owned by the first writer, granting the first two.

    Function-scoped and torn down with its dataset, because the two
    cases below need the same name under different ownership values and
    a bucket's `object_ownership` decides what its tree already holds.
    """
    one, two, _stranger = writers

    def make(ownership):
        return s3_bucket(
            BUCKET,
            dataset=DATASET,
            owner=one.username,
            object_ownership=ownership,
            grants=[user_grant(one.uid), user_grant(two.uid)],
        )

    return make


def test_object_writer_records_the_account_that_wrote(writers, owned, daemon):
    """Under `OBJECT_WRITER` a publish is the writer's own file.

    The daemon makes the share root the owner's at `0755`, nothing is
    opened on it, and neither grantee is fenced by it — which is the
    `S3` permissions model saying the filesystem's answer is not
    consulted. What the value *does* decide is the uid each object
    lands under, and that is read off the tree.
    """
    one, two, _stranger = writers
    with owned("OBJECT_WRITER"), s3_service():
        a, b = client_for(one.key, daemon), client_for(two.key, daemon)
        assert BUCKET in [x["Name"] for x in a.list_buckets()["Buckets"]]

        root = call("filesystem.stat", f"/mnt/{DATASET}/s3data")
        assert (root["uid"], root["mode"] & 0o777) == (one.uid, 0o755), "left as the daemon made it"

        a.put_object(Bucket=BUCKET, Key="pfx/hello.txt", Body=b"from a")
        assert a.get_object(Bucket=BUCKET, Key="pfx/hello.txt")["Body"].read() == b"from a"
        assert ssh(f"cat /mnt/{DATASET}/s3data/pfx/hello.txt") == "from a"
        assert call("filesystem.stat", f"/mnt/{DATASET}/s3data/pfx/hello.txt")["uid"] == one.uid

        # The second grantee writes into the first's prefix and over the
        # first's object, and is fenced by neither.
        b.put_object(Bucket=BUCKET, Key="pfx/other.txt", Body=b"from b")
        b.put_object(Bucket=BUCKET, Key="pfx/hello.txt", Body=b"b over a")
        assert a.get_object(Bucket=BUCKET, Key="pfx/hello.txt")["Body"].read() == b"b over a"
        assert call("filesystem.stat", f"/mnt/{DATASET}/s3data/pfx/hello.txt")["uid"] == two.uid

        b.delete_object(Bucket=BUCKET, Key="pfx/hello.txt")
        assert [o["Key"] for o in a.list_objects_v2(Bucket=BUCKET)["Contents"]] == ["pfx/other.txt"]


def test_bucket_owner_enforced_writes_as_the_owner(writers, owned, daemon):
    """Under `BUCKET_OWNER_ENFORCED` the grants are the whole of it.

    The same two grantees write into the share root the daemon made the
    owner-only tree of, and over each other, and everything they publish
    lands on disk as the *owner's* rather than the writer's. A key with
    no grant is still refused, since the value moves the uid the kernel
    sees and not who is authorized.
    """
    one, two, stranger = writers
    with owned("BUCKET_OWNER_ENFORCED"), s3_service():
        a, b, nobody = (client_for(k.key, daemon) for k in (one, two, stranger))
        a.put_object(Bucket=BUCKET, Key="pfx/hello.txt", Body=b"from a")
        b.put_object(Bucket=BUCKET, Key="pfx/hello.txt", Body=b"b over a")
        assert a.get_object(Bucket=BUCKET, Key="pfx/hello.txt")["Body"].read() == b"b over a"

        with pytest.raises(Exception, match="AccessDenied"):
            nobody.put_object(Bucket=BUCKET, Key="pfx/hello.txt", Body=b"from nobody")

        assert ssh(f"cat /mnt/{DATASET}/s3data/pfx/hello.txt") == "b over a"
        for path in ("s3data", "s3data/pfx", "s3data/pfx/hello.txt"):
            assert call("filesystem.stat", f"/mnt/{DATASET}/{path}")["uid"] == one.uid, path


def test_an_enforced_bucket_has_no_acl_surface(writers, owned, daemon):
    """`BUCKET_OWNER_ENFORCED` disables ACLs, which is half of what it is.

    The read is still supported — AWS keeps `GetBucketAcl` answering a
    fixed owner document — and every write is refused
    `AccessControlListNotSupported`. A bucket that stored an ACL here
    would be storing a record nothing consults.
    """
    one, _two, _stranger = writers
    with owned("BUCKET_OWNER_ENFORCED"), s3_service():
        a = client_for(one.key, daemon)
        assert a.get_bucket_acl(Bucket=BUCKET)["Owner"]["ID"]
        with pytest.raises(Exception) as caught:
            a.put_bucket_acl(Bucket=BUCKET, ACL="public-read")
        assert code_of(caught.value) == "AccessControlListNotSupported"


# ── the conditional table, on the session's preferred bucket ─────────


@pytest.fixture(scope="module")
def preferred(buckets):
    """The `BUCKET_OWNER_PREFERRED` bucket, or a skip.

    Owned by the alt account and written by the main one, which its
    grant row admits — a bucket whose owner is already its writer
    answers both ways identically and could show nothing.
    """
    name = buckets.get("preferred")
    if not name:
        pytest.skip("no preferred bucket: the session could not provision one")
    return name


@pytest.fixture(scope="module")
def owners(s3, preferred):
    """`(writer_id, bucket_owner_id)`, read off served documents.

    Neither is assumed. The writer's is what an ordinary write records,
    and the bucket owner's is what a `bucket-owner-full-control` write
    records — so a deployment whose canonical-id seed is whatever it is
    is covered rather than skipped.
    """
    mine, theirs = "own/probe-writer.bin", "own/probe-owner.bin"
    s3.put_object(Bucket=preferred, Key=mine, Body=b"w")
    s3.put_object(Bucket=preferred, Key=theirs, Body=b"o", ACL="bucket-owner-full-control")
    writer = owner_of(s3, preferred, mine)
    owner = owner_of(s3, preferred, theirs)
    assert writer != owner, f"the preferred bucket is owned by its writer ({writer}): it cannot show ownership moving"
    return writer, owner


def owner_of(s3, bucket, key, **kwargs):
    """The `<Owner>` id `GetObjectAcl` renders for one version."""
    return s3.get_object_acl(Bucket=bucket, Key=key, **kwargs)["Owner"]["ID"]


def test_a_plain_write_stays_the_writers(s3, preferred, owners):
    writer, _ = owners
    key = "own/put-object-no-acl"
    s3.put_object(Bucket=preferred, Key=key, Body=b"mine")
    assert owner_of(s3, preferred, key) == writer


def test_the_offered_write_goes_to_the_bucket_owner(s3, preferred, owners):
    """And the writer keeps access, which is the point of the canned
    value: ownership moved, so the writer's `FULL_CONTROL` is now an
    explicit grant rather than the implicit pair an owner holds."""
    writer, owner = owners
    key = "own/put-object-bucket-owner-full-control"
    s3.put_object(Bucket=preferred, Key=key, Body=b"theirs", ACL="bucket-owner-full-control")
    assert owner_of(s3, preferred, key) == owner

    grants = s3.get_object_acl(Bucket=preferred, Key=key)["Grants"]
    ids = [(g["Grantee"].get("ID"), g["Permission"]) for g in grants]
    assert (writer, "FULL_CONTROL") in ids, ids
    assert s3.get_object(Bucket=preferred, Key=key)["Body"].read() == b"theirs"


@pytest.mark.parametrize("canned", ["private", "public-read", "bucket-owner-read"])
def test_every_other_canned_value_keeps_the_writer(s3, preferred, owners, canned):
    """`bucket-owner-read` is the interesting one: it names the bucket
    owner and still does not transfer, because AWS moves ownership on
    the one canned spelling and not on whoever a grant mentions."""
    writer, _ = owners
    key = f"own/put-object-{canned}"
    s3.put_object(Bucket=preferred, Key=key, Body=b"mine", ACL=canned)
    assert owner_of(s3, preferred, key) == writer


def test_a_grant_header_naming_the_owner_is_not_a_transfer(s3, preferred, owners):
    """The grant headers spell permissions, never ownership.

    The two spellings reach the same stored record and differ in exactly
    this, so a change that transferred on the expanded grants would pass
    every case above.
    """
    writer, owner = owners
    key = "own/grant-full-control"
    s3.put_object(Bucket=preferred, Key=key, Body=b"mine", GrantFullControl=f"id={owner}")
    assert owner_of(s3, preferred, key) == writer


def test_a_copy_decides_ownership_by_its_own_acl(s3, preferred, owners):
    """A copy's ACL is the request's, never the source's."""
    writer, owner = owners
    src = "own/copy-source"
    s3.put_object(Bucket=preferred, Key=src, Body=b"src", ACL="bucket-owner-full-control")
    assert owner_of(s3, preferred, src) == owner

    source = {"Bucket": preferred, "Key": src}
    s3.copy_object(Bucket=preferred, Key="own/copy-no-acl", CopySource=source)
    assert owner_of(s3, preferred, "own/copy-no-acl") == writer

    s3.copy_object(
        Bucket=preferred,
        Key="own/copy-offered",
        CopySource=source,
        ACL="bucket-owner-full-control",
    )
    assert owner_of(s3, preferred, "own/copy-offered") == owner


def test_a_multipart_upload_publishes_under_the_owner_it_declared(s3, preferred, owners):
    """The decision is the *create's*, made before a part exists and
    resolved at Complete, so this is the one path where the answer has
    to survive on disk. `ListParts` renders it while the upload is still
    open — as `Owner`, beside the `Initiator` who opened it, which stays
    the caller either way."""
    writer, owner = owners
    body = b"m" * (5 * 1024 * 1024)
    for canned, want in ((None, writer), ("bucket-owner-full-control", owner)):
        key = f"own/mpu-{canned or 'no-acl'}"
        extra = {"ACL": canned} if canned else {}
        upload = s3.create_multipart_upload(Bucket=preferred, Key=key, **extra)["UploadId"]

        listed = s3.list_parts(Bucket=preferred, Key=key, UploadId=upload)
        assert listed["Owner"]["ID"] == want, canned
        assert listed["Initiator"]["ID"] == writer, "the initiator is who opened it"

        part = s3.upload_part(Bucket=preferred, Key=key, UploadId=upload, PartNumber=1, Body=body)
        s3.complete_multipart_upload(
            Bucket=preferred,
            Key=key,
            UploadId=upload,
            MultipartUpload={"Parts": [{"ETag": part["ETag"], "PartNumber": 1}]},
        )
        assert owner_of(s3, preferred, key) == want, canned


def test_the_listing_reports_the_owner_the_write_recorded(s3, preferred, owners):
    """A second surface on the same fact: the ACL document and the
    listing row are read from different records, and a divergence
    between them is what a stored owner field would have introduced."""
    writer, owner = owners
    prefix = "own/listed/"
    s3.put_object(Bucket=preferred, Key=prefix + "mine", Body=b"a")
    s3.put_object(Bucket=preferred, Key=prefix + "theirs", Body=b"b", ACL="bucket-owner-full-control")

    listed = s3.list_objects_v2(Bucket=preferred, Prefix=prefix, FetchOwner=True)
    got = {row["Key"]: row["Owner"]["ID"] for row in listed.get("Contents", [])}
    assert got.get(prefix + "mine") == writer, got
    assert got.get(prefix + "theirs") == owner, got


def test_the_probe_reports_the_configured_ownership(s3, preferred, bucket):
    """`GetBucketOwnershipControls` reads the row, not a constant."""
    rules = s3.get_bucket_ownership_controls(Bucket=preferred)["OwnershipControls"]["Rules"]
    assert rules[0]["ObjectOwnership"] == "BucketOwnerPreferred", rules

    other = s3.get_bucket_ownership_controls(Bucket=bucket)["OwnershipControls"]["Rules"]
    assert other[0]["ObjectOwnership"] == "ObjectWriter", other
