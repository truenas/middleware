"""S3 ACLs: the document surface, and the access it actually grants.

Two halves, and the second is the one that matters. The document half
asserts what a canned value or an XML body stores and reads back. The
enforcement half runs as `alt_s3` — authenticated, holding no grant row
anywhere — so every allow it observes travelled through the stored
record and nothing else. That is the deferral this server's
authorization rests on, and it is unprovable with a single principal.

Three of this server's divergences shape the cases:

- **Anonymous requests stay 403 whatever the ACL stores.** An `AllUsers`
  grant is stored and rendered, never effective unsigned.
- **The bucket owner keeps implicit access to everything in the bucket**,
  so owner-lockout cases assert against the *second* principal's objects
  rather than the owner's.
- **Grantee ids are this deployment's canonical ids.** Names are labels
  and ids decide; nothing resolves an id to a passwd row before storing
  it.
"""

import time

import pytest
from s3_client import ALL_USERS, AUTHENTICATED_USERS, code_of, grants_of, status_of


def refused(call, *codes):
    """Run `call`, assert it raised one of `codes`, return the error."""
    with pytest.raises(Exception) as caught:
        call()
    assert code_of(caught.value) in codes or str(status_of(caught.value)) in codes, (
        f"expected {codes}, got {code_of(caught.value)} / {status_of(caught.value)}"
    )
    return caught.value


def past_a_second_boundary():
    """Wait until a later whole second, before asserting a timestamp.

    `LastModified` is whole seconds on the wire, so two calls issued back
    to back land in the same second and "the timestamp did not move" is
    true of a timestamp that moved by milliseconds. 1.1 s is the smallest
    wait that crosses a boundary whatever the phase.
    """
    time.sleep(1.1)


@pytest.fixture
def private_bucket(s3, bucket):
    """The bucket handed back private, whatever the case stored.

    The enforcement matrix opens the shared bucket up; every case that
    does so leaves through here, so the modules after this one still meet
    the bucket the session provisioned.
    """
    yield bucket
    s3.put_bucket_acl(Bucket=bucket, ACL="private")


@pytest.fixture
def alt_id(s3, bucket, alt_s3, accounts):
    """The alt principal's canonical id, learned rather than derived.

    The low hex digits are the uid and the rest is the deployment's seed,
    so the id is read off a served document and then *proved* to name the
    alt principal: a grant is stored for it and the alt credential reads
    the document back. A refused read after an accepted grant is a defect
    — the daemon never learned the credential, or the deferral itself —
    and fails rather than skips.
    """
    key = "acl/id-probe.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"i")
    owner = s3.get_object_acl(Bucket=bucket, Key=key)["Owner"]["ID"]
    derived = owner[:56] + format(accounts["alt"].uid, "08x")
    s3.put_object_acl(Bucket=bucket, Key=key, GrantReadACP=f"id={derived}")
    alt_s3.get_object_acl(Bucket=bucket, Key=key)
    return derived


# ── the object document ──────────────────────────────────────────────


def test_a_default_object_acl_is_owner_full_control(s3, bucket):
    """A plain write stores no record and answers the owner document."""
    key = "acl/default.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    doc = s3.get_object_acl(Bucket=bucket, Key=key)
    owner = doc["Owner"]["ID"]
    assert len(owner) == 64, f"a canonical id is 64 hex: {owner}"
    assert owner == owner.lower(), owner
    assert doc["Owner"]["DisplayName"].startswith("TrueNAS User Unix Id "), doc["Owner"]
    assert grants_of(doc) == [(owner, "FULL_CONTROL")], grants_of(doc)


def test_each_canned_value_expands_in_a_pinned_order(s3, bucket):
    """Group grants first, the writer's FULL_CONTROL last.

    The two bucket-owner values collapse to the default where writer and
    bucket owner are one uid, as they are here.
    """
    key = "acl/canned.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    owner = s3.get_object_acl(Bucket=bucket, Key=key)["Owner"]["ID"]

    for canned, want in (
        ("private", [(owner, "FULL_CONTROL")]),
        ("public-read", [(ALL_USERS, "READ"), (owner, "FULL_CONTROL")]),
        (
            "public-read-write",
            [(ALL_USERS, "READ"), (ALL_USERS, "WRITE"), (owner, "FULL_CONTROL")],
        ),
        ("authenticated-read", [(AUTHENTICATED_USERS, "READ"), (owner, "FULL_CONTROL")]),
        ("bucket-owner-read", [(owner, "FULL_CONTROL")]),
        ("bucket-owner-full-control", [(owner, "FULL_CONTROL")]),
    ):
        s3.put_object(Bucket=bucket, Key=key, Body=b"x", ACL=canned)
        doc = s3.get_object_acl(Bucket=bucket, Key=key)
        assert grants_of(doc) == want, f"{canned}: {grants_of(doc)}"


@pytest.mark.parametrize("perm", ["READ", "WRITE", "READ_ACP", "WRITE_ACP", "FULL_CONTROL"])
def test_each_permission_round_trips_through_the_xml_body(s3, bucket, perm):
    """The owner is unchanged and FULL_CONTROL is never decomposed."""
    key = "acl/xml.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    owner = s3.get_object_acl(Bucket=bucket, Key=key)["Owner"]["ID"]
    s3.put_object_acl(
        Bucket=bucket,
        Key=key,
        AccessControlPolicy={
            "Owner": {"ID": owner},
            "Grants": [{"Grantee": {"Type": "CanonicalUser", "ID": owner}, "Permission": perm}],
        },
    )
    assert grants_of(s3.get_object_acl(Bucket=bucket, Key=key)) == [(owner, perm)]


def test_a_put_object_acl_moves_neither_the_owner_nor_the_object(s3, bucket):
    """The ETag, Last-Modified and bytes all stand: a tag edit changes no
    byte of the object, so it may not move what identifies it."""
    key = "acl/attrs.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"held")
    before = s3.head_object(Bucket=bucket, Key=key)
    owner = s3.get_object_acl(Bucket=bucket, Key=key)["Owner"]["ID"]

    past_a_second_boundary()
    s3.put_object_acl(Bucket=bucket, Key=key, ACL="public-read")

    assert s3.get_object_acl(Bucket=bucket, Key=key)["Owner"]["ID"] == owner
    after = s3.head_object(Bucket=bucket, Key=key)
    assert before["ETag"] == after["ETag"]
    assert before["LastModified"] == after["LastModified"]
    assert s3.get_object(Bucket=bucket, Key=key)["Body"].read() == b"held"

    listed = s3.list_objects_v2(Bucket=bucket, Prefix=key)["Contents"]
    assert len(listed) == 1 and listed[0]["LastModified"] == before["LastModified"], listed
    s3.put_object_acl(Bucket=bucket, Key=key, ACL="private")


def test_the_header_grants_replace_the_default(s3, bucket):
    """`x-amz-grant-*` replaces the owner default and renders in header
    order — on a `PutObjectAcl` and on the write itself."""
    key = "acl/grants.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    owner = s3.get_object_acl(Bucket=bucket, Key=key)["Owner"]["ID"]

    s3.put_object_acl(Bucket=bucket, Key=key, GrantRead=f"id={owner}", GrantWrite=f"id={owner}")
    assert grants_of(s3.get_object_acl(Bucket=bucket, Key=key)) == [
        (owner, "READ"),
        (owner, "WRITE"),
    ]

    s3.put_object(Bucket=bucket, Key=key, Body=b"x", GrantReadACP=f"id={owner}")
    assert grants_of(s3.get_object_acl(Bucket=bucket, Key=key)) == [(owner, "READ_ACP")]


def test_a_group_grantee_round_trips_by_uri(s3, bucket):
    """A group grantee stores and renders as its URI, nothing else."""
    key = "acl/group.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    owner = s3.get_object_acl(Bucket=bucket, Key=key)["Owner"]["ID"]
    s3.put_object_acl(
        Bucket=bucket,
        Key=key,
        AccessControlPolicy={
            "Owner": {"ID": owner},
            "Grants": [{"Grantee": {"Type": "Group", "URI": AUTHENTICATED_USERS}, "Permission": "READ"}],
        },
    )
    doc = s3.get_object_acl(Bucket=bucket, Key=key)
    assert grants_of(doc) == [(AUTHENTICATED_USERS, "READ")]
    assert "DisplayName" not in doc["Grants"][0]["Grantee"], "a group renders no DisplayName"


def test_an_empty_grant_list_is_a_present_record(s3, bucket):
    """Distinct from absent: zero grants survive, the owner element still
    renders, and `private` restores the default."""
    key = "acl/revoked.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    owner = s3.get_object_acl(Bucket=bucket, Key=key)["Owner"]["ID"]

    s3.put_object_acl(Bucket=bucket, Key=key, AccessControlPolicy={"Owner": {"ID": owner}, "Grants": []})
    doc = s3.get_object_acl(Bucket=bucket, Key=key)
    assert grants_of(doc) == []
    assert doc["Owner"]["ID"] == owner

    s3.put_object_acl(Bucket=bucket, Key=key, ACL="private")
    assert grants_of(s3.get_object_acl(Bucket=bucket, Key=key)) == [(owner, "FULL_CONTROL")]


def test_every_acl_refusal_answers_before_anything_stores(s3, bucket):
    """Both spellings of every refusal, because they are separate code
    paths: a grant *header* is resolved by one routine and an
    `<AccessControlPolicy>` *body* by another, so a header case says
    nothing about the body."""
    key = "acl/refuse.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    owner = s3.get_object_acl(Bucket=bucket, Key=key)["Owner"]["ID"]

    err = refused(
        lambda: s3.put_object(Bucket=bucket, Key="acl/bad.bin", Body=b"x", ACL="public-rea"),
        "InvalidArgument",
    )
    assert status_of(err) == 400
    refused(lambda: s3.head_object(Bucket=bucket, Key="acl/bad.bin"), "404")

    refused(lambda: s3.put_object_acl(Bucket=bucket, Key=key, GrantRead="id=_foo"), "InvalidArgument")
    refused(
        lambda: s3.put_object_acl(Bucket=bucket, Key=key, GrantRead="emailAddress=no@such.example"),
        "UnresolvableGrantByEmailAddress",
    )

    # The same two through the body, which is the shape s3cmd's `setacl`
    # sends.
    refused(
        lambda: s3.put_object_acl(
            Bucket=bucket,
            Key=key,
            AccessControlPolicy={
                "Owner": {"ID": owner},
                "Grants": [{"Grantee": {"Type": "CanonicalUser", "ID": "_foo"}, "Permission": "FULL_CONTROL"}],
            },
        ),
        "InvalidArgument",
    )
    refused(
        lambda: s3.put_object_acl(
            Bucket=bucket,
            Key=key,
            AccessControlPolicy={
                "Owner": {"ID": owner},
                "Grants": [
                    {
                        "Grantee": {
                            "Type": "AmazonCustomerByEmail",
                            "EmailAddress": "no@such.example",
                        },
                        "Permission": "READ",
                    }
                ],
            },
        ),
        "UnresolvableGrantByEmailAddress",
    )

    # Two spellings of one instruction.
    refused(
        lambda: s3.put_object_acl(Bucket=bucket, Key=key, ACL="public-read", GrantRead=f"id={owner}"),
        "InvalidRequest",
    )

    # A body Owner naming someone else: the uid half flipped still parses
    # as a canonical id, of a different principal.
    wrong = owner[:-1] + ("1" if owner[-1] == "0" else "0")
    refused(
        lambda: s3.put_object_acl(Bucket=bucket, Key=key, AccessControlPolicy={"Owner": {"ID": wrong}, "Grants": []}),
        "MalformedACLError",
    )

    # Past the hundred-grant cap the document refuses whole.
    grant = {"Grantee": {"Type": "CanonicalUser", "ID": owner}, "Permission": "READ"}
    refused(
        lambda: s3.put_object_acl(
            Bucket=bucket,
            Key=key,
            AccessControlPolicy={"Owner": {"ID": owner}, "Grants": [grant] * 101},
        ),
        "MalformedACLError",
    )
    refused(lambda: s3.get_object_acl(Bucket=bucket, Key="acl/never.bin"), "NoSuchKey")

    # A directory marker stores a mkdir and no record for grants.
    refused(
        lambda: s3.put_object(Bucket=bucket, Key="acl/dir/", Body=b"", ACL="public-read"),
        "InvalidRequest",
    )

    # None of the above stored half a policy.
    assert grants_of(s3.get_object_acl(Bucket=bucket, Key=key)) == [(owner, "FULL_CONTROL")]


def test_a_multipart_create_acl_reaches_the_assembled_object(s3, bucket):
    """A create-time ACL is staged with the upload and stamps what
    Complete assembles."""
    key = "acl/assembled.bin"
    uid = s3.create_multipart_upload(Bucket=bucket, Key=key, ACL="public-read")["UploadId"]
    part = s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=1, Body=b"p" * (5 * 1024 * 1024))
    s3.complete_multipart_upload(
        Bucket=bucket,
        Key=key,
        UploadId=uid,
        MultipartUpload={"Parts": [{"PartNumber": 1, "ETag": part["ETag"]}]},
    )
    doc = s3.get_object_acl(Bucket=bucket, Key=key)
    assert grants_of(doc) == [(ALL_USERS, "READ"), (doc["Owner"]["ID"], "FULL_CONTROL")]


def test_a_copy_never_carries_the_source_acl(s3, bucket):
    """The destination's ACL is the request's or the default — never the
    source's."""
    src, dst = "acl/copy-src.bin", "acl/copy-dst.bin"
    s3.put_object(Bucket=bucket, Key=src, Body=b"x", ACL="public-read")
    s3.copy_object(Bucket=bucket, Key=dst, CopySource={"Bucket": bucket, "Key": src})
    doc = s3.get_object_acl(Bucket=bucket, Key=dst)
    assert grants_of(doc) == [(doc["Owner"]["ID"], "FULL_CONTROL")]


# ── the bucket document ──────────────────────────────────────────────


def test_a_default_bucket_acl_is_owner_full_control(s3, bucket):
    doc = s3.get_bucket_acl(Bucket=bucket)
    owner = doc["Owner"]["ID"]
    assert len(owner) == 64 and owner == owner.lower(), owner
    assert doc["Owner"]["DisplayName"].startswith("TrueNAS User Unix Id "), doc["Owner"]
    assert grants_of(doc) == [(owner, "FULL_CONTROL")]


def test_a_bucket_acl_round_trips_canned_and_xml(s3, private_bucket):
    bucket = private_bucket
    owner = s3.get_bucket_acl(Bucket=bucket)["Owner"]["ID"]
    s3.put_bucket_acl(Bucket=bucket, ACL="public-read")
    assert grants_of(s3.get_bucket_acl(Bucket=bucket)) == [
        (ALL_USERS, "READ"),
        (owner, "FULL_CONTROL"),
    ]

    for perm in ("READ", "WRITE", "READ_ACP", "WRITE_ACP", "FULL_CONTROL"):
        s3.put_bucket_acl(
            Bucket=bucket,
            AccessControlPolicy={
                "Owner": {"ID": owner},
                "Grants": [{"Grantee": {"Type": "CanonicalUser", "ID": owner}, "Permission": perm}],
            },
        )
        assert grants_of(s3.get_bucket_acl(Bucket=bucket)) == [(owner, perm)], perm


def test_the_bucket_owner_canned_values_are_refused(s3, private_bucket):
    """The canned vocabulary is the level's: `bucket-owner-read` and
    `bucket-owner-full-control` belong to the object writes.

    Against a writer who *is* the owner they expand to the default, whose
    spelling here is a record *removal* — so admitting them would let a
    request that named a grant silently delete the record it addressed.
    """
    bucket = private_bucket
    owner = s3.get_bucket_acl(Bucket=bucket)["Owner"]["ID"]
    s3.put_bucket_acl(Bucket=bucket, ACL="public-read")
    for canned in ("bucket-owner-read", "bucket-owner-full-control"):
        refused(lambda c=canned: s3.put_bucket_acl(Bucket=bucket, ACL=c), "InvalidArgument")
    assert grants_of(s3.get_bucket_acl(Bucket=bucket)) == [
        (ALL_USERS, "READ"),
        (owner, "FULL_CONTROL"),
    ]


def test_unsigned_acl_reads_stay_refused(daemon, s3, private_bucket):
    """An `AllUsers` grant is stored and rendered, never effective
    unsigned — the anonymous `?acl` read, and the read it would license,
    answer 403 like every unsigned request."""
    import ssl
    import urllib.error
    import urllib.request

    bucket = private_bucket
    s3.put_bucket_acl(Bucket=bucket, ACL="public-read")
    s3.put_object(Bucket=bucket, Key="acl/raw.bin", Body=b"x", ACL="public-read")

    if daemon.startswith("https://"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    else:
        opener = urllib.request.build_opener()

    for target in (
        f"{daemon}/{bucket}?acl",
        f"{daemon}/{bucket}/acl/raw.bin?acl",
        f"{daemon}/{bucket}/acl/raw.bin",
    ):
        try:
            opener.open(target, timeout=10)
            raised = None
        except urllib.error.HTTPError as err:
            raised = err.code
        assert raised == 403, f"{target}: expected 403, got {raised}"


# ── enforcement: the second principal ────────────────────────────────


def test_a_stranger_is_refused_by_the_default_acl(s3, alt_s3, bucket):
    """No rows, no record: the deferral lands on the default ACL and the
    default admits only the owner."""
    key = "acl/held.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"kept", ACL="private")

    refused(lambda: alt_s3.get_object(Bucket=bucket, Key=key), "AccessDenied")
    refused(lambda: alt_s3.head_object(Bucket=bucket, Key=key), "403")
    refused(lambda: alt_s3.get_object_acl(Bucket=bucket, Key=key), "AccessDenied")
    refused(lambda: alt_s3.put_object(Bucket=bucket, Key=key, Body=b"take"), "AccessDenied")
    refused(lambda: alt_s3.delete_object(Bucket=bucket, Key=key), "AccessDenied")
    refused(lambda: alt_s3.list_objects_v2(Bucket=bucket), "AccessDenied")


def test_an_object_read_grant_admits_the_stranger(s3, alt_s3, bucket):
    """`public-read` on the object opens exactly the object read — not
    the ACL, not the write path."""
    key = "acl/opened.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"open", ACL="public-read")

    assert alt_s3.get_object(Bucket=bucket, Key=key)["Body"].read() == b"open"
    alt_s3.head_object(Bucket=bucket, Key=key)
    refused(lambda: alt_s3.get_object_acl(Bucket=bucket, Key=key), "AccessDenied")
    refused(lambda: alt_s3.put_object(Bucket=bucket, Key=key, Body=b"no"), "AccessDenied")

    # AuthenticatedUsers admits any signed caller the same way.
    s3.put_object_acl(Bucket=bucket, Key=key, ACL="authenticated-read")
    alt_s3.get_object(Bucket=bucket, Key=key)

    # And back to private closes it again.
    s3.put_object_acl(Bucket=bucket, Key=key, ACL="private")
    refused(lambda: alt_s3.get_object(Bucket=bucket, Key=key), "AccessDenied")


def test_a_direct_user_grant_admits_by_id(s3, alt_s3, private_bucket, alt_id):
    """Ids decide, and the id is learned from a served document rather
    than resolved from a name."""
    bucket = private_bucket
    key = "acl/granted.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"g")
    refused(lambda: alt_s3.get_object(Bucket=bucket, Key=key), "AccessDenied")

    s3.put_object_acl(Bucket=bucket, Key=key, GrantRead=f"id={alt_id}")
    assert alt_s3.get_object(Bucket=bucket, Key=key)["Body"].read() == b"g"

    # READ_ACP by id opens the document read alone.
    refused(lambda: alt_s3.get_object_acl(Bucket=bucket, Key=key), "AccessDenied")
    s3.put_object_acl(Bucket=bucket, Key=key, GrantReadACP=f"id={alt_id}")
    alt_s3.get_object_acl(Bucket=bucket, Key=key)


def test_bucket_write_is_what_gates_the_write_family(s3, alt_s3, private_bucket):
    """An object WRITE grant stays stored but inert; the *bucket's* WRITE
    is the gate for Put, Delete and a multipart create."""
    bucket = private_bucket
    key = "acl/write-gated.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    owner = s3.get_object_acl(Bucket=bucket, Key=key)["Owner"]["ID"]

    s3.put_object_acl(
        Bucket=bucket,
        Key=key,
        AccessControlPolicy={
            "Owner": {"ID": owner},
            "Grants": [{"Grantee": {"Type": "Group", "URI": ALL_USERS}, "Permission": "WRITE"}],
        },
    )
    refused(lambda: alt_s3.put_object(Bucket=bucket, Key=key, Body=b"no"), "AccessDenied")

    s3.put_bucket_acl(Bucket=bucket, ACL="public-read-write")
    alt_s3.list_objects_v2(Bucket=bucket)
    alt_s3.head_bucket(Bucket=bucket)
    alt_s3.put_object(Bucket=bucket, Key="acl/alt-new.bin", Body=b"mine")
    alt_s3.delete_object(Bucket=bucket, Key="acl/alt-new.bin")

    upload = alt_s3.create_multipart_upload(Bucket=bucket, Key="acl/alt-upload.bin")
    part = alt_s3.upload_part(
        Bucket=bucket,
        Key="acl/alt-upload.bin",
        UploadId=upload["UploadId"],
        PartNumber=1,
        Body=b"p" * (5 * 1024 * 1024),
    )
    alt_s3.complete_multipart_upload(
        Bucket=bucket,
        Key="acl/alt-upload.bin",
        UploadId=upload["UploadId"],
        MultipartUpload={"Parts": [{"PartNumber": 1, "ETag": part["ETag"]}]},
    )
    alt_s3.delete_object(Bucket=bucket, Key="acl/alt-upload.bin")

    # Revocation closes the path again.
    s3.put_bucket_acl(Bucket=bucket, ACL="private")
    refused(lambda: alt_s3.put_object(Bucket=bucket, Key="acl/alt-late.bin", Body=b"no"), "AccessDenied")
    refused(lambda: alt_s3.create_multipart_upload(Bucket=bucket, Key="acl/alt-late.bin"), "AccessDenied")


def test_the_writer_owns_what_they_wrote(s3, alt_s3, private_bucket):
    """An admitted write records the caller as the object's owner, and
    their implicit ACP pair holds on it — including revoking their own
    READ and climbing back out."""
    bucket = private_bucket
    s3.put_bucket_acl(Bucket=bucket, ACL="public-read-write")
    key = "acl/theirs.bin"
    alt_s3.put_object(Bucket=bucket, Key=key, Body=b"theirs")

    doc = alt_s3.get_object_acl(Bucket=bucket, Key=key)
    alt = doc["Owner"]["ID"]
    assert grants_of(doc) == [(alt, "FULL_CONTROL")]

    # Revoke everything; READ goes, the implicit pair stays.
    alt_s3.put_object_acl(Bucket=bucket, Key=key, AccessControlPolicy={"Owner": {"ID": alt}, "Grants": []})
    refused(lambda: alt_s3.get_object(Bucket=bucket, Key=key), "AccessDenied")
    alt_s3.get_object_acl(Bucket=bucket, Key=key)
    alt_s3.put_object_acl(Bucket=bucket, Key=key, ACL="private")
    assert alt_s3.get_object(Bucket=bucket, Key=key)["Body"].read() == b"theirs"


def test_a_copy_needs_source_read_and_dest_write(s3, alt_s3, private_bucket):
    """A copy is two verdicts, each from its own record."""
    bucket = private_bucket
    s3.put_object(Bucket=bucket, Key="acl/src-closed.bin", Body=b"c")
    s3.put_object(Bucket=bucket, Key="acl/src-open.bin", Body=b"o", ACL="public-read")

    # Dest WRITE missing: refused whatever the source says.
    refused(
        lambda: alt_s3.copy_object(
            Bucket=bucket, Key="acl/dst.bin", CopySource={"Bucket": bucket, "Key": "acl/src-open.bin"}
        ),
        "AccessDenied",
    )

    s3.put_bucket_acl(Bucket=bucket, ACL="public-read-write")
    # Source READ missing: still refused.
    refused(
        lambda: alt_s3.copy_object(
            Bucket=bucket,
            Key="acl/dst.bin",
            CopySource={"Bucket": bucket, "Key": "acl/src-closed.bin"},
        ),
        "AccessDenied",
    )

    alt_s3.copy_object(Bucket=bucket, Key="acl/dst.bin", CopySource={"Bucket": bucket, "Key": "acl/src-open.bin"})
    got = alt_s3.get_object_acl(Bucket=bucket, Key="acl/dst.bin")
    assert grants_of(got) == [(got["Owner"]["ID"], "FULL_CONTROL")]


def test_a_batch_delete_answers_per_row_for_the_ungranted(s3, alt_s3, bucket):
    """A deferred batch the record refuses answers per key under 200 —
    the operation's own reporting shape — and deletes nothing."""
    keys = ["acl/batch-a.bin", "acl/batch-b.bin"]
    for key in keys:
        s3.put_object(Bucket=bucket, Key=key, Body=b"x")

    out = alt_s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in keys]})
    assert {(e["Key"], e["Code"]) for e in out.get("Errors", [])} == {(k, "AccessDenied") for k in keys}
    assert not out.get("Deleted"), out
    for key in keys:
        s3.head_object(Bucket=bucket, Key=key)


def test_full_control_implies_the_acp_pair(s3, alt_s3, private_bucket, alt_id):
    """FULL_CONTROL admits everything its four parts would, never
    decomposed on the wire, and the owner element never moves."""
    bucket = private_bucket
    key = "acl/fc.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    owner = s3.get_object_acl(Bucket=bucket, Key=key)["Owner"]["ID"]
    s3.put_object_acl(Bucket=bucket, Key=key, GrantFullControl=f"id={alt_id}")

    doc = alt_s3.get_object_acl(Bucket=bucket, Key=key)
    assert grants_of(doc) == [(alt_id, "FULL_CONTROL")]
    alt_s3.get_object(Bucket=bucket, Key=key)
    alt_s3.put_object_acl(Bucket=bucket, Key=key, GrantRead=f"id={alt_id}", GrantWriteACP=f"id={alt_id}")

    doc = s3.get_object_acl(Bucket=bucket, Key=key)
    assert doc["Owner"]["ID"] == owner, "the owner element never moves"
    assert grants_of(doc) == [(alt_id, "READ"), (alt_id, "WRITE_ACP")]


def test_the_bucket_grants_admit_exactly_their_operation_family(s3, alt_s3, private_bucket, alt_id):
    """The five bucket permissions, one at a time: READ opens the
    listings and HeadBucket, WRITE the write family, the ACP pair its own
    document — and none opens a neighbour's door."""
    bucket = private_bucket
    bucket_owner = s3.get_bucket_acl(Bucket=bucket)["Owner"]["ID"]

    probes = {
        "list": lambda: alt_s3.list_objects_v2(Bucket=bucket),
        "head": lambda: alt_s3.head_bucket(Bucket=bucket),
        "put": lambda: alt_s3.put_object(Bucket=bucket, Key="acl/matrix.bin", Body=b"m"),
        "delete": lambda: alt_s3.delete_object(Bucket=bucket, Key="acl/matrix.bin"),
        "read_acp": lambda: alt_s3.get_bucket_acl(Bucket=bucket),
        "write_acp": lambda: alt_s3.put_bucket_acl(Bucket=bucket, GrantRead=f"id={alt_id}"),
    }
    table = [
        ("GrantRead", {"list", "head"}),
        ("GrantReadACP", {"read_acp"}),
        ("GrantWrite", {"put", "delete"}),
        ("GrantWriteACP", {"write_acp"}),
        ("GrantFullControl", set(probes)),
    ]

    for grant_kw, allowed in table:
        s3.put_bucket_acl(Bucket=bucket, **{grant_kw: f"id={alt_id}"})
        for name, run in probes.items():
            if name in allowed:
                run()
            else:
                # A HEAD refusal has no body to carry the code, so
                # botocore names it by status alone.
                refused(run, "AccessDenied", "403")
        # The write_acp probe rewrote the record; put it back under the
        # one grant this round is about before the next probe reads it.
        if "write_acp" in allowed:
            s3.put_bucket_acl(Bucket=bucket, **{grant_kw: f"id={alt_id}"})

    s3.put_bucket_acl(Bucket=bucket, ACL="private")
    assert s3.get_bucket_acl(Bucket=bucket)["Owner"]["ID"] == bucket_owner


def test_versioned_acls_are_per_version(s3, buckets):
    """`?versionId` addresses one version's record; the versionless put
    lands on the current version; a fresh PUT starts at the default."""
    versioned = buckets["locked"]
    key = "acl/versioned.bin"
    old = s3.put_object(Bucket=versioned, Key=key, Body=b"one")["VersionId"]
    new = s3.put_object(Bucket=versioned, Key=key, Body=b"two")["VersionId"]

    s3.put_object_acl(Bucket=versioned, Key=key, VersionId=old, ACL="public-read")
    assert (ALL_USERS, "READ") in grants_of(s3.get_object_acl(Bucket=versioned, Key=key, VersionId=old))
    doc = s3.get_object_acl(Bucket=versioned, Key=key, VersionId=new)
    assert grants_of(doc) == [(doc["Owner"]["ID"], "FULL_CONTROL")], "the current version's default"

    # Versionless lands on the current version.
    s3.put_object_acl(Bucket=versioned, Key=key, ACL="authenticated-read")
    assert (AUTHENTICATED_USERS, "READ") in grants_of(s3.get_object_acl(Bucket=versioned, Key=key, VersionId=new))
    assert (ALL_USERS, "READ") in grants_of(s3.get_object_acl(Bucket=versioned, Key=key, VersionId=old))

    fresh = s3.put_object(Bucket=versioned, Key=key, Body=b"three")["VersionId"]
    doc = s3.get_object_acl(Bucket=versioned, Key=key, VersionId=fresh)
    assert grants_of(doc) == [(doc["Owner"]["ID"], "FULL_CONTROL")]
