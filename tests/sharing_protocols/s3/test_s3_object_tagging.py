"""Object tagging: the three operations, the grammar, and the ETag they
may not move.

A tag edit changes no byte of the object, so it may not move the ETag —
AWS's own rule, and the reason the set is stored away from the object's
own record rather than on it. Half this file is the grammar's boundary,
asserted from the side that must be accepted: every refusal below
answers one code, so a validator that stopped checking one of them would
still look correct against the other three.
"""

import pytest
from s3_client import code_of, payload, status_of

PREFIX = "tags/"


def count_header(response):
    """`x-amz-tagging-count` off the wire, not off the response model.

    Read raw because the modeled field is the SDK's: botocore carries
    `TagCount` on `GetObjectOutput` in every version and on
    `HeadObjectOutput` only in later ones, so a modeled read asserts the
    installed botocore rather than the header the server sent.
    """
    headers = response["ResponseMetadata"]["HTTPHeaders"]
    return {k.lower(): v for k, v in headers.items()}.get("x-amz-tagging-count")


def tagset_of(s3, bucket, key, **kwargs):
    return s3.get_object_tagging(Bucket=bucket, Key=key, **kwargs)["TagSet"]


def test_a_never_tagged_object_answers_an_empty_set(s3, bucket):
    """An empty set, not a 404: the object is there and it has no tags,
    which are different facts from the key being absent."""
    key = f"{PREFIX}untagged.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    assert tagset_of(s3, bucket, key) == []


def test_the_three_operations_round_trip(s3, bucket):
    key = f"{PREFIX}obj.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=payload(2048))

    s3.put_object_tagging(
        Bucket=bucket,
        Key=key,
        Tagging={"TagSet": [{"Key": "project", "Value": "borealis"}, {"Key": "tier", "Value": "cold"}]},
    )
    assert {t["Key"]: t["Value"] for t in tagset_of(s3, bucket, key)} == {
        "project": "borealis",
        "tier": "cold",
    }

    # Replaced whole, never merged.
    s3.put_object_tagging(Bucket=bucket, Key=key, Tagging={"TagSet": [{"Key": "project", "Value": "borealis"}]})
    assert len(tagset_of(s3, bucket, key)) == 1

    # A cleared set reads the same as one that never existed.
    s3.delete_object_tagging(Bucket=bucket, Key=key)
    assert tagset_of(s3, bucket, key) == []


def test_a_tag_edit_moves_neither_the_etag_nor_the_bytes(s3, bucket):
    """AWS's rule: *"the ETag reflects changes only to the contents of an
    object, not its metadata"*. The on-disk placement exists to guarantee
    that rather than repair it."""
    key = f"{PREFIX}etag.bin"
    body = payload(2048)
    before = s3.put_object(Bucket=bucket, Key=key, Body=body)["ETag"]

    s3.put_object_tagging(Bucket=bucket, Key=key, Tagging={"TagSet": [{"Key": "a", "Value": "1"}]})
    assert s3.head_object(Bucket=bucket, Key=key)["ETag"] == before
    assert s3.get_object(Bucket=bucket, Key=key)["Body"].read() == body

    s3.delete_object_tagging(Bucket=bucket, Key=key)
    assert s3.head_object(Bucket=bucket, Key=key)["ETag"] == before, "nor does the clear"


def test_the_count_header_follows_the_set(s3, bucket):
    """Present with the size of the stored set, omitted at zero — so
    never-tagged and cleared answer the same."""
    key = f"{PREFIX}counted.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    assert count_header(s3.head_object(Bucket=bucket, Key=key)) is None

    s3.put_object_tagging(
        Bucket=bucket,
        Key=key,
        Tagging={"TagSet": [{"Key": "a", "Value": "1"}, {"Key": "b", "Value": "2"}]},
    )
    assert count_header(s3.head_object(Bucket=bucket, Key=key)) == "2"
    got = s3.get_object(Bucket=bucket, Key=key)
    assert count_header(got) == "2"
    got["Body"].read()

    s3.delete_object_tagging(Bucket=bucket, Key=key)
    assert count_header(s3.head_object(Bucket=bucket, Key=key)) is None


def test_tagging_a_missing_key_is_absence(s3, bucket):
    with pytest.raises(Exception) as caught:
        s3.get_object_tagging(Bucket=bucket, Key=f"{PREFIX}absent.bin")
    assert status_of(caught.value) == 404
    assert code_of(caught.value) == "NoSuchKey"


# ── the grammar, from the side that must be accepted ─────────────────


@pytest.mark.parametrize(
    "tagset,why",
    [
        ([{"Key": f"k{i}", "Value": "v"} for i in range(10)], "ten pairs"),
        ([{"Key": "k" * 128, "Value": "v"}], "a key of exactly 128"),
        ([{"Key": "k", "Value": "v" * 256}], "a value of exactly 256"),
        ([{"Key": "k", "Value": ""}], "an empty value"),
    ],
)
def test_a_set_at_the_limit_is_stored(s3, bucket, tagset, why):
    """AWS's documented maxima are inclusive, and an empty value is a tag.

    The empty value is the case a shared screen gets wrong: an empty
    *key* is inadmissible and an empty value is not, so a validator that
    folded the two would refuse a legal set.
    """
    key = f"{PREFIX}limits.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    s3.put_object_tagging(Bucket=bucket, Key=key, Tagging={"TagSet": tagset})

    stored = tagset_of(s3, bucket, key)
    assert len(stored) == len(tagset), why
    assert {t["Key"]: t["Value"] for t in stored} == {t["Key"]: t["Value"] for t in tagset}, why


@pytest.mark.parametrize(
    "tagset,why",
    [
        ([{"Key": "k" * 129, "Value": "v"}], "a key over 128"),
        ([{"Key": "k", "Value": "v" * 257}], "a value over 256"),
        ([{"Key": f"k{i}", "Value": "v"} for i in range(11)], "eleven pairs"),
        ([{"Key": "d", "Value": "1"}, {"Key": "d", "Value": "2"}], "a duplicated key"),
    ],
)
def test_the_grammar_refuses(s3, bucket, tagset, why):
    """`InvalidTag` for each way a set can be inadmissible.

    All four are one code, which is the risk: a validator that stopped
    checking one of them would still answer `InvalidTag` for the other
    three and look correct.
    """
    key = f"{PREFIX}refused.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    with pytest.raises(Exception) as caught:
        s3.put_object_tagging(Bucket=bucket, Key=key, Tagging={"TagSet": tagset})
    assert status_of(caught.value) == 400, why
    assert code_of(caught.value) == "InvalidTag", why


def test_the_limits_are_counted_in_characters_not_bytes(s3, bucket):
    """A 128-character CJK key is 384 bytes, and it is admissible.

    The limits AWS documents are counted in characters and a stored
    record's budget is counted in bytes, so a screen applied after the
    encode would refuse a conformant set. The refusal one character later
    is asserted beside it, so this cannot pass by the limit having been
    dropped altogether.
    """
    key = f"{PREFIX}characters.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    wide = "測" * 128
    assert len(wide.encode()) == 384

    s3.put_object_tagging(Bucket=bucket, Key=key, Tagging={"TagSet": [{"Key": wide, "Value": "測" * 256}]})
    assert tagset_of(s3, bucket, key) == [{"Key": wide, "Value": "測" * 256}]

    with pytest.raises(Exception) as caught:
        s3.put_object_tagging(Bucket=bucket, Key=key, Tagging={"TagSet": [{"Key": "測" * 129, "Value": "v"}]})
    assert code_of(caught.value) == "InvalidTag"


def test_a_letter_is_admissible_where_a_symbol_is_not(s3, bucket):
    """AWS's tag charset is `[\\p{L}\\p{Z}\\p{N}_.:/=+\\-@]`, and the two
    halves of that are worth telling apart.

    A CJK letter is `\\p{L}` and belongs; an emoji is `So` and does not.
    Implementations get this wrong in both directions, so the *accepting*
    case is what pins this to the reference rather than to the strictest
    thing that passes.
    """
    key = f"{PREFIX}charset.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")

    s3.put_object_tagging(Bucket=bucket, Key=key, Tagging={"TagSet": [{"Key": "分類", "Value": "測試元資料"}]})
    assert tagset_of(s3, bucket, key) == [{"Key": "分類", "Value": "測試元資料"}]

    with pytest.raises(Exception) as caught:
        s3.put_object_tagging(Bucket=bucket, Key=key, Tagging={"TagSet": [{"Key": "k", "Value": "\U0001f3af"}]})
    assert status_of(caught.value) == 400
    assert code_of(caught.value) == "InvalidTag"


# ── the set a write carries with it ──────────────────────────────────


def test_a_tagging_header_stores_the_set_the_write_named(s3, bucket):
    """`x-amz-tagging` on a PUT is honored, not refused.

    `GetObjectTagging` is asserted rather than the count header alone,
    because a count is also what an unrelated set would answer.
    """
    key = f"{PREFIX}header.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"body", Tagging="project=borealis&tier=cold+storage")
    assert {t["Key"]: t["Value"] for t in tagset_of(s3, bucket, key)} == {
        "project": "borealis",
        "tier": "cold storage",
    }
    assert count_header(s3.get_object(Bucket=bucket, Key=key)) == "2"


def test_a_bare_key_in_the_header_is_a_tag_with_an_empty_value(s3, bucket):
    """`x-amz-tagging: foo=bar&bar` stores two tags, one valueless.

    The bare `bar` is the half a parser reusing the path rule rather than
    the form rule gets wrong: it is a key with an empty value, not a
    malformed pair. Compared as a set — S3 documents no order for
    `TagSet`.
    """
    key = f"{PREFIX}bare-key.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"A" * 100, Tagging="foo=bar&bar")
    assert {(t["Key"], t["Value"]) for t in tagset_of(s3, bucket, key)} == {("foo", "bar"), ("bar", "")}
    assert s3.get_object(Bucket=bucket, Key=key)["Body"].read() == b"A" * 100


@pytest.mark.parametrize(
    "tagging,why",
    [
        ("=v", "an empty key"),
        ("k=a#b", "outside the tag charset"),
        ("k=one&k=two", "the same key twice"),
        ("&".join(f"k{n}=v" for n in range(11)), "eleven pairs"),
        (f"{'k' * 129}=v", "a key one character over"),
        (f"k={'v' * 257}", "a value one character over"),
    ],
)
def test_the_header_form_takes_every_screen_the_document_takes(s3, bucket, tagging, why):
    """A set that got through here would be stored and answered `200`, so
    a screen present in one spelling and missing from the other is a way
    to store what AWS refuses."""
    with pytest.raises(Exception) as caught:
        s3.put_object(Bucket=bucket, Key=f"{PREFIX}header-refused.bin", Body=b"body", Tagging=tagging)
    assert code_of(caught.value) == "InvalidTag", why

    with pytest.raises(Exception) as caught:
        s3.head_object(Bucket=bucket, Key=f"{PREFIX}header-refused.bin")
    assert status_of(caught.value) == 404, "nothing was stored"


def test_an_overwrite_does_not_inherit_the_tags_it_replaced(s3, bucket):
    """Obvious, and it was wrong once: a tag set is keyed by the version
    entry it belongs to, and where two writes share an entry the second
    inherited the first's set unless the destroy that retires the slot
    also retired its key."""
    key = f"{PREFIX}overwrite.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"first", Tagging="a=b")
    assert tagset_of(s3, bucket, key) == [{"Key": "a", "Value": "b"}]

    s3.put_object(Bucket=bucket, Key=key, Body=b"second")
    assert tagset_of(s3, bucket, key) == []
    assert count_header(s3.get_object(Bucket=bucket, Key=key)) is None


def test_a_copy_replaces_or_carries_by_its_directive(s3, bucket):
    """`REPLACE` takes the header's set; `COPY` takes the source's.

    Both arms against the same source, which is the only way to tell a
    working `REPLACE` from one that silently carried the source's set
    anyway. `REPLACE` with no header names the empty set — the only
    spelling of "copy this object without its tags".
    """
    src = f"{PREFIX}copy-src.bin"
    s3.put_object(Bucket=bucket, Key=src, Body=b"body", Tagging="a=one")
    source = {"Bucket": bucket, "Key": src}

    carried = f"{PREFIX}copy-carried.bin"
    s3.copy_object(Bucket=bucket, Key=carried, CopySource=source)
    assert tagset_of(s3, bucket, carried) == [{"Key": "a", "Value": "one"}]

    replaced = f"{PREFIX}copy-replaced.bin"
    s3.copy_object(Bucket=bucket, Key=replaced, CopySource=source, TaggingDirective="REPLACE", Tagging="b=two")
    assert tagset_of(s3, bucket, replaced) == [{"Key": "b", "Value": "two"}]

    cleared = f"{PREFIX}copy-cleared.bin"
    s3.copy_object(Bucket=bucket, Key=cleared, CopySource=source, TaggingDirective="REPLACE")
    assert tagset_of(s3, bucket, cleared) == []


def test_a_multipart_create_carries_its_set_to_the_completed_object(s3, bucket):
    """The set cannot be stored where it belongs at create time — the
    record is keyed by the version id and none is drawn until the
    publish — so it waits on the upload and Complete re-keys it.

    That step can be dropped without any other case noticing, since every
    part and the object itself are correct either way.
    """
    key = f"{PREFIX}multipart.bin"
    uid = s3.create_multipart_upload(Bucket=bucket, Key=key, Tagging="run=nightly")["UploadId"]
    part = s3.upload_part(Bucket=bucket, Key=key, UploadId=uid, PartNumber=1, Body=b"x" * (5 * 1024 * 1024))
    s3.complete_multipart_upload(
        Bucket=bucket,
        Key=key,
        UploadId=uid,
        MultipartUpload={"Parts": [{"ETag": part["ETag"], "PartNumber": 1}]},
    )
    assert tagset_of(s3, bucket, key) == [{"Key": "run", "Value": "nightly"}]


# ── directory keys ───────────────────────────────────────────────────


def test_a_directory_key_answers_an_empty_tag_set(s3, bucket):
    """`GET key/?tagging` is 200 with an empty set, not 404.

    A directory key stores no tag set — the record is keyed for a regular
    file's versions and a directory has none — but `key/` *is* an object
    this server answers 200 for on HEAD and GET, and a 404 from the
    tagging read alone would make it the one verb that disagreed about
    whether the key is there.
    """
    key = f"{PREFIX}folder/"
    s3.put_object(Bucket=bucket, Key=key)
    assert s3.head_object(Bucket=bucket, Key=key)["ContentLength"] == 0
    assert tagset_of(s3, bucket, key) == []

    # Absence is still absence.
    with pytest.raises(Exception) as caught:
        s3.get_object_tagging(Bucket=bucket, Key=f"{PREFIX}never-made/")
    assert code_of(caught.value) == "NoSuchKey"

    # And a regular file is not reachable through the directory probe.
    s3.put_object(Bucket=bucket, Key=f"{PREFIX}plain.bin", Body=b"x")
    with pytest.raises(Exception) as caught:
        s3.get_object_tagging(Bucket=bucket, Key=f"{PREFIX}plain.bin/")
    assert code_of(caught.value) == "NoSuchKey"


def test_a_directory_key_refuses_the_tag_writes(s3, bucket):
    """The read answers the empty set; these do not answer at all — a set
    written here would be one no reader could ever reach."""
    key = f"{PREFIX}refuses/"
    s3.put_object(Bucket=bucket, Key=key)

    for label, call in (
        (
            "put",
            lambda: s3.put_object_tagging(Bucket=bucket, Key=key, Tagging={"TagSet": [{"Key": "a", "Value": "1"}]}),
        ),
        ("delete", lambda: s3.delete_object_tagging(Bucket=bucket, Key=key)),
    ):
        with pytest.raises(Exception) as caught:
            call()
        assert code_of(caught.value) == "NoSuchKey", label

    assert tagset_of(s3, bucket, key) == []
