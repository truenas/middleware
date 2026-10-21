"""Buckets with the DATASET layout: an existing dataset served read-only.

``conftest`` wrote ``a.txt`` and ``docs/2026/b.txt`` in the dataset and
``child/c.txt`` in a child dataset mounted under it, then set
``readonly=on``.
"""

import botocore.exceptions
import pytest
from s3_client import code_of, status_of

TREE = ["a.txt", "docs/2026/b.txt"]
"""Every file in the exported dataset itself, in key order."""

CHILD = "child"
"""The directory on which the child dataset is mounted."""


@pytest.fixture(scope="module")
def export(buckets):
    return buckets["exported"]


def keys_of(page):
    return [c["Key"] for c in page.get("Contents", [])]


def groups_of(page):
    return [p["Prefix"] for p in page.get("CommonPrefixes", [])]


def listed(s3, bucket):
    keys = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        keys += keys_of(page)
    return keys


def refused(call):
    with pytest.raises(botocore.exceptions.ClientError) as caught:
        call()
    return status_of(caught.value), code_of(caught.value)


def test_the_tree_serves_as_foreign_files(s3, export):
    """Files are listed and served with a derived ETag, no version id and
    no tags. Directories appear only as prefixes."""
    assert listed(s3, export) == TREE
    page = s3.list_objects_v2(Bucket=export, Delimiter="/")
    assert keys_of(page) == ["a.txt"]
    assert groups_of(page) == ["docs/"]

    got = s3.get_object(Bucket=export, Key="a.txt")
    assert got["Body"].read() == b"alpha"
    assert got["ContentLength"] == 5
    assert "VersionId" not in got
    assert len(got["ETag"]) == 38, got["ETag"]
    assert s3.get_object_tagging(Bucket=export, Key="a.txt")["TagSet"] == []
    assert s3.get_bucket_versioning(Bucket=export).get("Status") is None


def test_the_control_directory_is_absent_by_name(s3, export):
    """.zfs at the root, and everything under it, returns 404. It never
    appears in a listing, for any prefix."""
    for key in [".zfs/", ".zfs/snapshot/", ".zfs/snapshot/x/y"]:
        assert refused(lambda key=key: s3.get_object(Bucket=export, Key=key)) == (404, "NoSuchKey"), key
    for prefix in [".zfs", ".zf", ".zfs/", ".zfs/snapshot/"]:
        page = s3.list_objects_v2(Bucket=export, Prefix=prefix)
        assert "Contents" not in page, (prefix, page)
        page = s3.list_objects_v2(Bucket=export, Prefix=prefix, Delimiter="/")
        assert "CommonPrefixes" not in page and "Contents" not in page, (prefix, page)


def test_a_dataset_mounted_beneath_is_not_entered(s3, export):
    """The child dataset is in no listing. Every read at or under it
    returns 404."""
    assert not [k for k in listed(s3, export) if k.startswith(f"{CHILD}/")]
    assert f"{CHILD}/" not in groups_of(s3.list_objects_v2(Bucket=export, Delimiter="/"))
    for kwargs in ({}, {"Delimiter": "/"}):
        page = s3.list_objects_v2(Bucket=export, Prefix=f"{CHILD}/", **kwargs)
        assert "Contents" not in page and "CommonPrefixes" not in page, page
    versions = s3.list_object_versions(Bucket=export)
    assert not [v["Key"] for v in versions.get("Versions", []) if v["Key"].startswith(f"{CHILD}/")]
    assert f"{CHILD}/" not in groups_of(s3.list_object_versions(Bucket=export, Delimiter="/"))
    for key in [f"{CHILD}/", f"{CHILD}/c.txt", f"{CHILD}/missing.txt"]:
        assert refused(lambda key=key: s3.get_object(Bucket=export, Key=key)) == (404, "NoSuchKey"), key
        assert refused(lambda key=key: s3.head_object(Bucket=export, Key=key))[0] == 404, key


def test_versions_lists_each_file_once_as_null(s3, export):
    """ListObjectVersions returns one null version per file, all IsLatest,
    no delete markers. ListMultipartUploads returns nothing."""
    page = s3.list_object_versions(Bucket=export)
    assert "DeleteMarkers" not in page
    versions = page.get("Versions", [])
    assert [v["Key"] for v in versions] == TREE
    assert all(v["VersionId"] == "null" and v["IsLatest"] for v in versions)
    assert "Uploads" not in s3.list_multipart_uploads(Bucket=export)
    assert s3.get_object(Bucket=export, Key="a.txt", VersionId="null")["ContentLength"] == 5
    assert refused(lambda: s3.get_object(Bucket=export, Key="a.txt", VersionId="0" * 32)) == (404, "NoSuchVersion")


def test_every_write_is_refused(s3, export):
    """Every write returns 403 AccessDenied, even for the bucket owner.
    DeleteObjects reports AccessDenied per key."""
    key = "a.txt"
    writes = {
        "PutObject": lambda: s3.put_object(Bucket=export, Key="export-new.txt", Body=b"x"),
        "PutObject key/": lambda: s3.put_object(Bucket=export, Key="export-dir/", Body=b""),
        "DeleteObject": lambda: s3.delete_object(Bucket=export, Key=key),
        "CopyObject": lambda: s3.copy_object(
            Bucket=export, Key="export-copy.txt", CopySource={"Bucket": export, "Key": key}
        ),
        "CreateMultipartUpload": lambda: s3.create_multipart_upload(Bucket=export, Key="export-m.bin"),
        "AbortMultipartUpload": lambda: s3.abort_multipart_upload(Bucket=export, Key="export-m.bin", UploadId="0" * 32),
        "PutObjectTagging": lambda: s3.put_object_tagging(
            Bucket=export, Key=key, Tagging={"TagSet": [{"Key": "a", "Value": "b"}]}
        ),
        "DeleteObjectTagging": lambda: s3.delete_object_tagging(Bucket=export, Key=key),
        "PutObjectRetention": lambda: s3.put_object_retention(
            Bucket=export, Key=key, Retention={"Mode": "GOVERNANCE", "RetainUntilDate": "2099-01-01T00:00:00Z"}
        ),
        "PutObjectLegalHold": lambda: s3.put_object_legal_hold(Bucket=export, Key=key, LegalHold={"Status": "ON"}),
    }
    for what, call in writes.items():
        assert refused(call) == (403, "AccessDenied"), what
    batch = s3.delete_objects(Bucket=export, Delete={"Objects": [{"Key": key}]})
    assert [e["Code"] for e in batch.get("Errors", [])] == ["AccessDenied"]
    assert not batch.get("Deleted")
    assert refused(lambda: s3.put_bucket_versioning(Bucket=export, VersioningConfiguration={"Status": "Enabled"})) == (
        403,
        "AccessDenied",
    )
