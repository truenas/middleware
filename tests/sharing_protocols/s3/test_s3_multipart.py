"""The multipart chain: what Complete refuses, and the two paging
surfaces a client recovers a session through.

A resumed backup lists the parts it already sent before deciding what to
send next, so a cursor that drops one silently re-uploads it and a
cursor that repeats one wastes the transfer. Both are invisible in a
single-page test, which is why the walks here run to exhaustion.

**Real 5 MiB parts.** The size floor is one of the rules under test and
an engine cannot be asked to enforce it against parts that never reach
it, so the cases that need a valid non-final part pay for the bytes.
"""

import contextlib

import pytest
from s3_client import CHUNK, code_of, digest, drain, raw_query, status_of

PREFIX = "mpu/"
PART = b"m" * (5 * CHUNK)


@pytest.fixture
def upload(s3, bucket):
    """A fresh session, aborted afterwards if the test left it open.

    **Aborting is not tidiness.** An upload outlives the test that made
    it until something forgets it, and `ListMultipartUploads` answers for
    the whole bucket — so a fixture that leaked one is invisible to every
    case addressing an upload by id and fatal to every case that lists
    them.
    """
    drain(s3, bucket, PREFIX)
    key = f"{PREFIX}target.bin"
    uid = s3.create_multipart_upload(Bucket=bucket, Key=key)["UploadId"]
    yield key, uid
    with contextlib.suppress(Exception):
        s3.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=uid)
    drain(s3, bucket, PREFIX)


def _complete(s3, bucket, key, uid, parts):
    return s3.complete_multipart_upload(Bucket=bucket, Key=key, UploadId=uid, MultipartUpload={"Parts": parts})


# ── the assembly ─────────────────────────────────────────────────────


def test_a_multipart_object_reads_back_as_its_parts_concatenated(s3, bucket, upload):
    """The assembly, checked by reading rather than by the 200.

    Two distinguishable parts, so a reversed or duplicated concatenation
    is visible in the bytes and not only in the length.
    """
    key, uid = upload
    bodies = [b"a" * (5 * CHUNK), b"b" * 1024]
    parts = []
    for n, body in enumerate(bodies, start=1):
        out = s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=n, Body=body)
        parts.append({"ETag": out["ETag"], "PartNumber": n})
    _complete(s3, bucket, key, uid, parts)

    got = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    assert digest(got) == digest(b"".join(bodies))


def test_a_single_short_part_completes(s3, bucket, upload):
    """The last part is exempt from the floor, and an upload of one part
    is all last part — so a tiny single-part upload is legal and its ETag
    is still the composite form."""
    key, uid = upload
    out = s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=1, Body=b"tiny")
    done = _complete(s3, bucket, key, uid, [{"ETag": out["ETag"], "PartNumber": 1}])
    assert done["ETag"].strip('"').endswith("-1")
    assert s3.get_object(Bucket=bucket, Key=key)["Body"].read() == b"tiny"


def test_the_create_content_headers_ride_to_completion(s3, bucket):
    """S3 takes the content headers at `CreateMultipartUpload` and
    applies them to what Complete publishes — the same storage a
    `PutObject`'s own get."""
    key = f"{PREFIX}dressed.bin"
    uid = s3.create_multipart_upload(
        Bucket=bucket,
        Key=key,
        CacheControl="max-age=321",
        ContentDisposition='attachment; filename="d.bin"',
    )["UploadId"]
    out = s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=1, Body=b"tiny")
    _complete(s3, bucket, key, uid, [{"ETag": out["ETag"], "PartNumber": 1}])

    head = s3.head_object(Bucket=bucket, Key=key)
    assert head["CacheControl"] == "max-age=321"
    assert head["ContentDisposition"] == 'attachment; filename="d.bin"'
    s3.delete_object(Bucket=bucket, Key=key)


# ── what Complete refuses ────────────────────────────────────────────


def test_an_unsorted_manifest_is_refused(s3, bucket, upload):
    """AWS assembles in part-number order whatever order the manifest
    names them in.

    A server that looped in manifest order would concatenate a scrambled
    object *and* compute its ETag over the same wrong order — a
    corruption its own digest agrees with. Refusing before any byte moves
    is the only answer that cannot do that.
    """
    key, uid = upload
    tags = []
    for n in (1, 2):
        out = s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=n, Body=PART)
        tags.append({"ETag": out["ETag"], "PartNumber": n})

    with pytest.raises(Exception) as caught:
        _complete(s3, bucket, key, uid, list(reversed(tags)))
    assert status_of(caught.value) == 400
    assert code_of(caught.value) == "InvalidPartOrder"


def test_a_manifest_naming_an_absent_part_is_refused(s3, bucket, upload):
    key, uid = upload
    out = s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=1, Body=PART)
    with pytest.raises(Exception) as caught:
        _complete(
            s3,
            bucket,
            key,
            uid,
            [{"ETag": out["ETag"], "PartNumber": 1}, {"ETag": out["ETag"], "PartNumber": 9}],
        )
    assert status_of(caught.value) == 400
    assert code_of(caught.value) == "InvalidPart"


def test_a_manifest_with_the_wrong_digest_is_refused(s3, bucket, upload):
    """The part is there and its bytes are right; the client's record of
    them is not. Accepting it would publish an object whose composite
    ETag the client cannot reproduce."""
    key, uid = upload
    s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=1, Body=PART)
    with pytest.raises(Exception) as caught:
        _complete(s3, bucket, key, uid, [{"ETag": '"' + "0" * 32 + '"', "PartNumber": 1}])
    assert status_of(caught.value) == 400
    assert code_of(caught.value) == "InvalidPart"


def test_a_rejected_complete_leaves_the_upload_usable(s3, bucket, upload):
    """AWS keeps a session alive after a refused Complete.

    The client fixes its manifest and tries again, so a server that
    consumed the session on the first refusal would make every
    correctable mistake terminal — and the upload could then be neither
    completed nor listed nor aborted.
    """
    key, uid = upload
    out = s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=1, Body=PART)
    with pytest.raises(Exception):
        _complete(s3, bucket, key, uid, [{"ETag": '"x"', "PartNumber": 1}])

    listed = s3.list_parts(Bucket=bucket, Key=key, UploadId=uid)
    assert [p["PartNumber"] for p in listed.get("Parts", [])] == [1]
    _complete(s3, bucket, key, uid, [{"ETag": out["ETag"], "PartNumber": 1}])
    assert s3.head_object(Bucket=bucket, Key=key)["ContentLength"] == len(PART)


def test_a_re_uploaded_part_number_replaces_that_part(s3, bucket, upload):
    """An SDK retries one failed part without restarting the upload.

    So the second write of a number must win, and Complete must accept
    the *new* digest and refuse the old one — a server that kept the
    first would answer 200 to a manifest naming bytes it did not store.
    """
    key, uid = upload
    first = s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=1, Body=PART)
    second = s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=1, Body=b"z" * (5 * CHUNK))
    assert first["ETag"] != second["ETag"]

    listed = s3.list_parts(Bucket=bucket, Key=key, UploadId=uid)
    assert [p["ETag"] for p in listed["Parts"]] == [second["ETag"]]

    with pytest.raises(Exception) as caught:
        _complete(s3, bucket, key, uid, [{"ETag": first["ETag"], "PartNumber": 1}])
    assert code_of(caught.value) == "InvalidPart"


def test_a_non_final_part_below_the_floor_is_refused(s3, bucket, upload):
    """5 MiB is the floor for every part but the last, and it is enforced
    at Complete — the only point where the server knows which part is
    last. A short part uploads with a 200 and fails there."""
    key, uid = upload
    tags = []
    for n, body in ((1, b"a" * 1024), (2, PART)):
        out = s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=n, Body=body)
        tags.append({"ETag": out["ETag"], "PartNumber": n})

    with pytest.raises(Exception) as caught:
        _complete(s3, bucket, key, uid, tags)
    assert status_of(caught.value) == 400
    assert code_of(caught.value) == "EntityTooSmall"


def test_an_empty_manifest_is_refused(s3, bucket, upload):
    """A Complete naming no parts would publish a 0-byte object."""
    key, uid = upload
    with pytest.raises(Exception) as caught:
        _complete(s3, bucket, key, uid, [])
    assert status_of(caught.value) >= 400


@pytest.mark.parametrize("number", [0, 10001])
def test_a_part_number_outside_the_range_is_refused(s3, bucket, upload, number):
    """1..=10000, and the refusal comes before any byte is read."""
    key, uid = upload
    with pytest.raises(Exception) as caught:
        s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=number, Body=b"x")
    assert status_of(caught.value) == 400
    assert code_of(caught.value) == "InvalidArgument"


def test_an_unknown_upload_id_is_no_such_upload(s3, bucket):
    """Every operation naming a session must agree on the answer: a
    client recovering from a crash calls them in any order and a bare 500
    from one of them is unactionable."""
    key = f"{PREFIX}ghost.bin"
    for call in (
        lambda: s3.upload_part(Bucket=bucket, Key=key, UploadId="nope", PartNumber=1, Body=b"x"),
        lambda: s3.list_parts(Bucket=bucket, Key=key, UploadId="nope"),
        lambda: s3.abort_multipart_upload(Bucket=bucket, Key=key, UploadId="nope"),
        lambda: s3.complete_multipart_upload(
            Bucket=bucket,
            Key=key,
            UploadId="nope",
            MultipartUpload={"Parts": [{"ETag": '"x"', "PartNumber": 1}]},
        ),
    ):
        with pytest.raises(Exception) as caught:
            call()
        assert status_of(caught.value) == 404
        assert code_of(caught.value) == "NoSuchUpload"


def test_an_abort_forgets_the_upload_and_publishes_nothing(s3, bucket):
    """Nothing at the key, nothing in the upload listing, and the id
    stops answering — the three ways a client can observe the session."""
    key = f"{PREFIX}aborted.bin"
    drain(s3, bucket, PREFIX)
    uid = s3.create_multipart_upload(Bucket=bucket, Key=key)["UploadId"]
    s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=1, Body=PART)
    s3.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=uid)

    open_ids = [u["UploadId"] for u in s3.list_multipart_uploads(Bucket=bucket).get("Uploads", [])]
    assert uid not in open_ids

    with pytest.raises(Exception) as caught:
        s3.list_parts(Bucket=bucket, Key=key, UploadId=uid)
    assert code_of(caught.value) == "NoSuchUpload"
    with pytest.raises(Exception) as caught:
        s3.head_object(Bucket=bucket, Key=key)
    assert status_of(caught.value) == 404


def test_a_completed_upload_stops_answering(s3, bucket, upload):
    """A retrying client must be able to tell "already done" from "still
    open", and the parts are unlinked by then, so answering the second
    Complete from them is not possible either."""
    key, uid = upload
    out = s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=1, Body=PART)
    manifest = [{"ETag": out["ETag"], "PartNumber": 1}]
    _complete(s3, bucket, key, uid, manifest)

    with pytest.raises(Exception) as caught:
        _complete(s3, bucket, key, uid, manifest)
    assert code_of(caught.value) == "NoSuchUpload"


# ── ListParts ────────────────────────────────────────────────────────


@pytest.fixture
def three_parts(s3, bucket, upload):
    """Two parts at the floor and a short tail."""
    key, uid = upload
    for n, body in ((1, PART), (2, PART), (3, b"tail")):
        s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=n, Body=body)
    return key, uid


def test_list_parts_answers_every_part_in_order(s3, bucket, three_parts):
    key, uid = three_parts
    got = s3.list_parts(Bucket=bucket, Key=key, UploadId=uid)
    assert [p["PartNumber"] for p in got["Parts"]] == [1, 2, 3]
    assert got["IsTruncated"] is False
    assert got["MaxParts"] == 1000
    assert got["Key"] == key
    assert got["UploadId"] == uid
    assert got["Parts"][0]["Size"] == len(PART)
    assert got["Parts"][2]["Size"] == len(b"tail")


def test_list_parts_pages_on_the_part_number_marker(s3, bucket, three_parts):
    """The cursor is asserted end to end rather than as one page: the
    walk must deliver each part exactly once, which is the property a
    resumed upload depends on. The marker names the last part *sent*,
    never the next one."""
    key, uid = three_parts
    seen, marker = [], 0
    while True:
        page = s3.list_parts(Bucket=bucket, Key=key, UploadId=uid, MaxParts=1, PartNumberMarker=marker)
        assert page["MaxParts"] == 1
        got = [p["PartNumber"] for p in page.get("Parts", [])]
        assert len(got) <= 1
        seen += got
        if not page["IsTruncated"]:
            break
        marker = page["NextPartNumberMarker"]
        assert marker == got[-1], "the marker must name the last part sent"
    assert seen == [1, 2, 3]


def test_a_part_number_marker_resumes_after_it(s3, bucket, three_parts):
    """The marker is exclusive: naming part 1 lists 2 and 3."""
    key, uid = three_parts
    got = s3.list_parts(Bucket=bucket, Key=key, UploadId=uid, PartNumberMarker=1)
    assert [p["PartNumber"] for p in got["Parts"]] == [2, 3]
    assert got["IsTruncated"] is False


def test_max_parts_zero_lists_nothing(s3, bucket, three_parts):
    """Zero is a cap, not a refusal, and the page is complete rather than
    truncated — a cap of zero is a shape no client sends by accident."""
    key, uid = three_parts
    got = s3.list_parts(Bucket=bucket, Key=key, UploadId=uid, MaxParts=0)
    assert got.get("Parts", []) == []
    assert got["IsTruncated"] is False


def test_a_non_numeric_max_parts_is_refused(s3, bucket, three_parts):
    """Sent raw: boto3 will not model a `max-parts` that is not a number,
    and a hand-rolled client is exactly what sends one."""
    key, uid = three_parts
    resp = raw_query(s3, bucket, {"uploadId": uid, "max-parts": "abc"}, key=key)
    assert resp.status_code == 400
    assert "<Code>InvalidArgument</Code>" in resp.text


def test_list_parts_for_another_key_is_no_such_upload(s3, bucket, three_parts):
    """An upload id belongs to a key, so presenting it against a
    different one is not a listing of nothing — it is a different upload,
    and there is none."""
    _key, uid = three_parts
    with pytest.raises(Exception) as caught:
        s3.list_parts(Bucket=bucket, Key=f"{PREFIX}other.bin", UploadId=uid)
    assert status_of(caught.value) == 404
    assert code_of(caught.value) == "NoSuchUpload"


# ── ListMultipartUploads ─────────────────────────────────────────────


@pytest.fixture
def spare_upload(s3, bucket):
    """A second open upload, under a prefix of its own."""
    key = "other/two.bin"
    uid = s3.create_multipart_upload(Bucket=bucket, Key=key)["UploadId"]
    yield key
    with contextlib.suppress(Exception):
        s3.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=uid)


def test_list_uploads_answers_the_open_ones(s3, bucket, upload, spare_upload):
    """A superset rather than an exact list: this operation answers for
    the whole bucket, so pinning it to an exact set would make the case
    fail for something another module left open."""
    key, uid = upload
    got = s3.list_multipart_uploads(Bucket=bucket)
    assert {key, spare_upload} <= {u["Key"] for u in got["Uploads"]}
    assert any(u["UploadId"] == uid and u["Key"] == key for u in got["Uploads"])


def test_list_uploads_caps_on_max_uploads(s3, bucket, upload, spare_upload):
    got = s3.list_multipart_uploads(Bucket=bucket, MaxUploads=1)
    assert len(got["Uploads"]) == 1
    assert got["IsTruncated"] is True


def test_list_uploads_filters_on_a_prefix(s3, bucket, upload, spare_upload):
    """The prefix is what makes this one exact: it selects the upload
    this test made and nothing else in the bucket."""
    key, uid = upload
    got = s3.list_multipart_uploads(Bucket=bucket, Prefix=PREFIX)
    assert [u["Key"] for u in got["Uploads"]] == [key]
    assert [u["UploadId"] for u in got["Uploads"]] == [uid]

    empty = s3.list_multipart_uploads(Bucket=bucket, Prefix="zzz")
    assert empty.get("Uploads", []) == []
    assert empty["IsTruncated"] is False


def test_a_delimiter_folds_uploads_into_prefixes(s3, bucket, upload, spare_upload):
    """The same folding the object listings do, on the same argument — an
    upload under a prefix is a group, not a row."""
    key, _uid = upload
    got = s3.list_multipart_uploads(Bucket=bucket, Delimiter="/")
    assert not {u["Key"] for u in got.get("Uploads", [])} & {key, spare_upload}
    assert {PREFIX, "other/"} <= {p["Prefix"] for p in got["CommonPrefixes"]}
    assert got["Delimiter"] == "/"


# ── UploadPartCopy ───────────────────────────────────────────────────


@pytest.fixture
def copy_source(s3, bucket):
    key = f"{PREFIX}upc-source.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=bytes((i * 7 + 11) % 251 for i in range(6 * CHUNK)))
    yield key
    s3.delete_object(Bucket=bucket, Key=key)


@pytest.mark.parametrize(
    "bad",
    [
        "byte=100-200",  # the unit, singular
        "bytes=invalid-range",
        "bytes=200-100",  # last below first
        "bytes=-2-300",
        "bytes=aa-12",
        "bytes=12-aa",
        "bytes=bb-",
        "bytes=-100",  # suffix form: `Range` has it, this header does not
        "bytes=100-",  # open end: nothing here knows the size
        "bytes=0-99, 200-299",  # multi-range: likewise
    ],
)
def test_the_copy_source_range_grammar_is_both_ends_or_nothing(s3, bucket, upload, copy_source, bad):
    """`bytes=first-last`, both ends required, and nothing else.

    A lenient parser turns each of these into a range the client did not
    ask for, and a part is the one place nothing downstream would catch
    it: the digest is minted, so wrong bytes still answer 200.
    """
    key, uid = upload
    with pytest.raises(Exception) as caught:
        s3.upload_part_copy(
            Bucket=bucket,
            Key=key,
            UploadId=uid,
            PartNumber=1,
            CopySource=f"{bucket}/{copy_source}",
            CopySourceRange=bad,
        )
    assert status_of(caught.value) == 400, bad
    assert code_of(caught.value) == "InvalidArgument", bad


def test_a_copy_range_may_not_reach_the_last_byte_plus_one(s3, bucket, upload, copy_source):
    """The range is inclusive at both ends, so byte N of an N-byte object
    does not exist and the request names one byte too many.

    `InvalidRange`, not `InvalidArgument`: a malformed *grammar* is the
    case above and an end past the source is this one, and the two are
    different failures. Off by one here copies a short part and answers
    200.
    """
    key, uid = upload
    size = 6 * CHUNK
    for rng in (f"bytes=100-{size + 5}", f"bytes={size + 250}-{size + 2000}", f"bytes=100-{size}"):
        with pytest.raises(Exception) as caught:
            s3.upload_part_copy(
                Bucket=bucket,
                Key=key,
                UploadId=uid,
                PartNumber=1,
                CopySource=f"{bucket}/{copy_source}",
                CopySourceRange=rng,
            )
        assert code_of(caught.value) == "InvalidRange", rng

    # And the last byte itself is fine, which makes the above a boundary
    # rather than a blanket refusal.
    out = s3.upload_part_copy(
        Bucket=bucket,
        Key=key,
        UploadId=uid,
        PartNumber=1,
        CopySource=f"{bucket}/{copy_source}",
        CopySourceRange=f"bytes=100-{size - 1}",
    )
    assert "ETag" in out["CopyPartResult"]


def test_list_parts_echoes_the_etag_the_copy_returned(s3, bucket, upload, copy_source):
    """A server that answers one ETag and stores another passes every
    other case here and then fails Complete, which checks the manifest
    against what it stored. The size must be the range's, too."""
    key, uid = upload
    out = s3.upload_part_copy(
        Bucket=bucket,
        Key=key,
        UploadId=uid,
        PartNumber=1,
        CopySource=f"{bucket}/{copy_source}",
        CopySourceRange="bytes=0-1023",
    )
    etag = out["CopyPartResult"]["ETag"]

    listed = s3.list_parts(Bucket=bucket, Key=key, UploadId=uid)["Parts"]
    assert len(listed) == 1
    assert listed[0]["PartNumber"] == 1
    assert listed[0]["Size"] == 1024
    assert listed[0]["ETag"] == etag


def test_the_copy_part_etag_is_in_the_body_and_not_a_header(s3, bucket, upload, copy_source):
    """`UploadPart` answers an `ETag` header; this call answers a
    `<CopyPartResult>` document and no header. A client reading the
    header would have nothing to put in its Complete manifest."""
    key, uid = upload
    out = s3.upload_part_copy(Bucket=bucket, Key=key, UploadId=uid, PartNumber=1, CopySource=f"{bucket}/{copy_source}")
    headers = out["ResponseMetadata"]["HTTPHeaders"]
    assert "etag" not in headers, headers.get("etag")

    bare = out["CopyPartResult"]["ETag"].strip('"')
    assert len(bare) == 32
    assert all(c in "0123456789abcdef" for c in bare)


def test_an_upload_holding_a_copied_part_is_not_a_composite(s3, bucket, upload, copy_source):
    """The divergence the design rests on.

    A composite ETag is a construction a client holding the bytes and the
    boundaries can redo. A copied part's digest is minted, not hashed, so
    a composite over it would be a claim wearing that shape — the object
    takes a minted identity instead, and gives up the `-N` with it.
    """
    key, uid = upload
    sent = b"s" * (5 * CHUNK)
    first = s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=1, Body=sent)
    second = s3.upload_part_copy(
        Bucket=bucket,
        Key=key,
        UploadId=uid,
        PartNumber=2,
        CopySource=f"{bucket}/{copy_source}",
        CopySourceRange="bytes=0-1023",
    )
    done = _complete(
        s3,
        bucket,
        key,
        uid,
        [
            {"PartNumber": 1, "ETag": first["ETag"]},
            {"PartNumber": 2, "ETag": second["CopyPartResult"]["ETag"]},
        ],
    )
    etag = done["ETag"].strip('"')
    assert len(etag) == 36, etag
    assert etag.count("-") == 4, etag
    assert not etag.endswith("-2"), etag

    got = s3.get_object(Bucket=bucket, Key=key)
    assert got["ETag"].strip('"') == etag, "GET echoes what Complete answered"


def test_a_copied_part_carries_no_checksum(s3, bucket, upload, copy_source):
    """This server reads nothing to make a copied part, so there is no
    checksum to report — `ListParts` must answer no `Checksum*` field
    rather than an empty or invented one."""
    key, uid = upload
    s3.upload_part_copy(Bucket=bucket, Key=key, UploadId=uid, PartNumber=1, CopySource=f"{bucket}/{copy_source}")
    part = s3.list_parts(Bucket=bucket, Key=key, UploadId=uid)["Parts"][0]
    for field in (
        "ChecksumCRC32",
        "ChecksumCRC32C",
        "ChecksumSHA1",
        "ChecksumSHA256",
        "ChecksumCRC64NVME",
    ):
        assert field not in part, f"{field}: {part.get(field)!r}"


def test_an_empty_source_names_no_part(s3, bucket, upload):
    """A zero-byte source would produce a zero-byte part, which
    Complete's size floor would then meet as the last part and accept."""
    key, uid = upload
    src = f"{PREFIX}upc-empty.bin"
    s3.put_object(Bucket=bucket, Key=src, Body=b"")
    with pytest.raises(Exception) as caught:
        s3.upload_part_copy(Bucket=bucket, Key=key, UploadId=uid, PartNumber=1, CopySource=f"{bucket}/{src}")
    assert code_of(caught.value) == "InvalidRequest"


# ── ?partNumber on a read ────────────────────────────────────────────


@pytest.fixture(scope="module")
def assembled(s3, bucket):
    """A three-part object, completed, and the bytes it should hold."""
    key = f"{PREFIX}assembled.bin"
    uid = s3.create_multipart_upload(Bucket=bucket, Key=key)["UploadId"]
    blob, parts = b"", []
    for number, size in enumerate([5 * CHUNK, 5 * CHUNK, CHUNK], 1):
        body = bytes((i * 7 + 11) % 251 for i in range(size))
        blob += body
        tag = s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=number, Body=body)["ETag"]
        parts.append({"ETag": tag, "PartNumber": number})
    etag = _complete(s3, bucket, key, uid, parts)["ETag"]
    yield key, blob, etag
    s3.delete_object(Bucket=bucket, Key=key)


def test_the_object_assembled(s3, bucket, assembled):
    """The control: without it every refusal below is ambiguous.

    A `416` for part 1 means the divergence only if the object really was
    assembled from three parts, so the composite ETag and the full length
    are asserted first.
    """
    key, blob, etag = assembled
    assert etag.endswith('-3"'), etag
    head = s3.head_object(Bucket=bucket, Key=key)
    assert head["ContentLength"] == len(blob)
    assert head["ETag"] == etag


@pytest.mark.parametrize("number", [1, 2, 3, 4])
def test_a_part_of_an_assembled_object_is_refused(s3, bucket, assembled, number):
    """`416 InvalidPartNumber` for every `N`, part 1 included.

    S3 keeps a multipart object's part boundaries because S3 never
    concatenates; this format does concatenate, so a finished object is a
    flat byte range and there is no window table left to project a part
    from. Part 1 is what makes this a divergence rather than a rounding:
    AWS answers it with the first part's bytes.
    """
    key, _blob, _etag = assembled
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=key, PartNumber=number)
    assert status_of(caught.value) == 416, number
    assert code_of(caught.value) == "InvalidPartNumber", number


def test_the_same_bytes_are_reachable_by_range(s3, bucket, assembled):
    """What a client gives up, and what it uses instead.

    The argument for the divergence is that the bytes are still
    addressable — by `Range`, which is what mainstream clients send
    anyway. That claim is only true if a window over a part boundary
    reads correctly, so the second part is fetched by offset here.
    """
    key, blob, _etag = assembled
    start, end = 5 * CHUNK, 10 * CHUNK - 1
    got = s3.get_object(Bucket=bucket, Key=key, Range=f"bytes={start}-{end}")
    assert got["ResponseMetadata"]["HTTPStatusCode"] == 206
    assert got["Body"].read() == blob[start : end + 1]


def test_part_one_of_an_unassembled_object_is_the_whole_of_it(s3, bucket):
    """The half that does *not* diverge, held down beside the half that
    does — a change that made the refusal universal would look like the
    divergence spreading rather than like a regression."""
    key = f"{PREFIX}single.bin"
    body = bytes((i * 7 + 11) % 251 for i in range(4096))
    stored = s3.put_object(Bucket=bucket, Key=key, Body=body)["ETag"]

    got = s3.get_object(Bucket=bucket, Key=key, PartNumber=1)
    assert got["ResponseMetadata"]["HTTPStatusCode"] == 206
    assert got["ContentLength"] == len(body)
    assert got["ETag"] == stored
    assert got["Body"].read() == body

    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=key, PartNumber=2)
    assert status_of(caught.value) == 416
    assert code_of(caught.value) == "InvalidPartNumber"


def test_a_part_read_before_completion_is_absent(s3, bucket, upload):
    """An upload in flight publishes no key, so a part read is a 404.

    The parts exist on disk and are listable through `ListParts`, which
    is exactly why the answer has to be `NoSuchKey`: a reader that could
    see an upload's parts could read a half-written object.
    """
    key, uid = upload
    s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=1, Body=PART)
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=key, PartNumber=1)
    assert status_of(caught.value) == 404
    assert code_of(caught.value) == "NoSuchKey"
