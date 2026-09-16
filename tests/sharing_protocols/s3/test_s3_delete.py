"""DeleteObject and DeleteObjects: idempotence, and the batch's shape.

Both verbs forgive a key that is not there, which is what makes an SDK's
retry of a delete safe. The batch adds a reporting contract on top of
that — one verdict per row, positionally — and a `Quiet` flag whose
whole purpose is a thousand-row response that is not a thousand rows
long.
"""

import base64
import hashlib

import pytest
from s3_client import code_of, raw_request, status_of

PREFIX = "del/"


def test_a_delete_removes_the_key_and_repeats_harmlessly(s3, bucket):
    key = f"{PREFIX}one.txt"
    s3.put_object(Bucket=bucket, Key=key, Body=b"doomed")
    s3.delete_object(Bucket=bucket, Key=key)

    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=key)
    assert status_of(caught.value) == 404
    assert code_of(caught.value) == "NoSuchKey"

    # A second delete of the same key, and of one never written, both
    # succeed — which is what makes a retry safe.
    s3.delete_object(Bucket=bucket, Key=key)
    s3.delete_object(Bucket=bucket, Key=f"{PREFIX}never-written")


def test_a_directory_marker_deletes_like_a_key(s3, bucket):
    s3.put_object(Bucket=bucket, Key=f"{PREFIX}mark/", Body=b"")
    s3.delete_object(Bucket=bucket, Key=f"{PREFIX}mark/")
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=f"{PREFIX}mark/")
    assert status_of(caught.value) == 404


def test_a_batch_answers_every_row_and_forgives_a_ghost(s3, bucket):
    keys = [f"{PREFIX}batch/{i}.bin" for i in range(8)]
    for key in keys:
        s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    s3.put_object(Bucket=bucket, Key=f"{PREFIX}batch/dir/", Body=b"")

    manifest = keys + [f"{PREFIX}batch/dir/", f"{PREFIX}batch/ghost"]
    out = s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in manifest]})

    assert sorted(d["Key"] for d in out.get("Deleted", [])) == sorted(manifest)
    assert not out.get("Errors"), out.get("Errors")
    assert s3.list_objects_v2(Bucket=bucket, Prefix=f"{PREFIX}batch/")["KeyCount"] == 0


def test_a_quiet_batch_reports_only_what_failed(s3, bucket):
    """A server that answered the same document either way would pass any
    test that only checked the status."""
    key = f"{PREFIX}quiet/present.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    out = s3.delete_objects(
        Bucket=bucket,
        Delete={"Objects": [{"Key": key}, {"Key": f"{PREFIX}quiet/absent.bin"}], "Quiet": True},
    )
    assert out.get("Deleted") is None, out.get("Deleted")
    assert out.get("Errors") is None, out.get("Errors")
    with pytest.raises(Exception):
        s3.head_object(Bucket=bucket, Key=key)

    # And loud, the same pair answers the row.
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    loud = s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": key}]})
    assert [d["Key"] for d in loud["Deleted"]] == [key]


def test_a_repeated_key_answers_once_per_row(s3, bucket):
    """The response is positional — a client matches rows to what it
    sent — so folding duplicates would shift every verdict after the
    fold."""
    key = f"{PREFIX}dupe/twice.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")
    out = s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": key}, {"Key": key}]})
    assert [d["Key"] for d in out["Deleted"]] == [key, key]
    assert "Errors" not in out


def test_a_stray_version_id_on_an_unversioned_bucket_is_a_no_op(s3, bucket):
    """On an unversioned bucket a stray version id names nothing, so a
    batch row carrying one is the idempotent success — never the
    `NoSuchVersion` a version walk would return. `null` names the object
    itself and removes it, as the single verb does."""
    stray = "0193f28c7a41748fbd3e22076c159af4"
    key = f"{PREFIX}batchver/keep.bin"
    s3.put_object(Bucket=bucket, Key=key, Body=b"x")

    out = s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": key, "VersionId": stray}]})
    assert [d["Key"] for d in out.get("Deleted", [])] == [key]
    assert "Errors" not in out, out.get("Errors")
    assert s3.get_object(Bucket=bucket, Key=key)["Body"].read() == b"x"

    single = s3.delete_object(Bucket=bucket, Key=key, VersionId=stray)
    assert single["ResponseMetadata"]["HTTPStatusCode"] == 204
    assert s3.get_object(Bucket=bucket, Key=key)["Body"].read() == b"x"

    out = s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": key, "VersionId": "null"}]})
    assert [d["Key"] for d in out.get("Deleted", [])] == [key]
    with pytest.raises(Exception) as caught:
        s3.get_object(Bucket=bucket, Key=key)
    assert code_of(caught.value) == "NoSuchKey"


def _batch(s3, bucket, body, with_digest=True):
    """A signed batch delete, with or without the `Content-MD5` it needs.

    Raw because the manifest sizes are the point: botocore builds the
    document from a list, and the thousand-and-first row is exactly the
    one an SDK is likely to refuse or page around before this server ever
    sees it.
    """
    headers = {}
    if with_digest:
        headers["Content-MD5"] = base64.b64encode(hashlib.md5(body).digest()).decode()
    return raw_request(s3, "POST", f"/{bucket}?delete", body=body, headers=headers)


def _manifest(keys):
    rows = b"".join(f"<Object><Key>{k}</Key></Object>".encode() for k in keys)
    return b"<Delete>" + rows + b"</Delete>"


def test_a_thousand_rows_is_the_ceiling(s3, bucket):
    """1000 accepted, 1001 refused — the boundary, not a magnitude.

    AWS's documented cap, and the reason it is enforced rather than
    trimmed: a manifest silently truncated at a thousand answers success
    for every row it never read. The keys need not exist, since a batch
    forgives an absent key and what is under test is the count alone.
    """
    keys = [f"{PREFIX}cap/{i:04d}.bin" for i in range(1001)]

    at = _batch(s3, bucket, _manifest(keys[:1000]))
    assert at.status_code == 200, at.content[:200]

    over = _batch(s3, bucket, _manifest(keys))
    assert over.status_code == 400
    assert b"MalformedXML" in over.content


def test_a_batch_without_content_md5_is_refused(s3, bucket):
    """`MissingContentMD5`: the one body this server will not take bare.

    A batch delete is the only request whose body names other objects, so
    a truncated one deletes a prefix of what was asked and answers
    success for it. The digest is what makes that undetectable case
    detectable.
    """
    manifest = _manifest([f"{PREFIX}absent.bin"])
    bare = _batch(s3, bucket, manifest, with_digest=False)
    assert bare.status_code == 400
    assert b"MissingContentMD5" in bare.content

    # The same manifest with the digest is accepted, so the refusal above
    # is the header and not the body.
    assert _batch(s3, bucket, manifest).status_code == 200
