"""A real file up and back down, byte for byte, through the transfer
manager.

Moved here from ``tests/api2/test_s3_bucket.py``. Nothing about it was
ever a middleware CRUD test: it drives boto3's own transfer manager
against a bucket middleware provisioned, takes both paths the manager
chooses between, and then reads the tree to see where the bytes landed
and who owns them.

**A tiny `put_object` proves neither path.** The manager splits above its
threshold, so a single PUT and a multipart are two different write paths
in the daemon — one streamed into place, one staged in the side tree and
published from it — and the bucket middleware provisioned has to carry
both. The ETag says which one the bytes took.
"""

import contextlib
import os
import re

from middlewared.test.integration.assets.s3 import s3_account, s3_bucket, s3_service, user_grant
from middlewared.test.integration.utils import call, pool, ssh
import pytest
from s3_client import client_for, md5_of, random_file

DATASET = f"{pool}/s3proto-transfer"
BUCKET = "s3proto-transfer"
KEY = "big/file.bin"


@pytest.fixture(scope="module")
def uploader():
    with s3_account("s3protoxfer") as account:
        yield account


@pytest.mark.parametrize(
    "size,threshold,parts,multipart_etag",
    [
        # One PUT: the transfer manager only splits above its threshold.
        (5 << 20, 8 << 20, 1, "COMPOSITE"),
        # Three parts: the multipart path, staged in the side tree the
        # daemon owns and published into s3data/ under the requester.
        (12 << 20, 5 << 20, 3, "COMPOSITE"),
        # The same three parts on a row that declines to hash them: the
        # transfer manager declares CRC32 and sends no Content-MD5, so
        # nothing gives the daemon a reason to, and the object is minted.
        (12 << 20, 5 << 20, 3, "MINTED"),
    ],
    ids=["single_put", "multipart", "minted_multipart"],
)
def test_a_file_survives_the_round_trip(uploader, daemon, size, threshold, parts, multipart_etag):
    """Up, down, and compared by digest — plus the tree underneath.

    The uploaded object lands in `s3data/` as the uploader's own file
    while the side tree beside it stays the daemon's, which is the
    separation the staging path depends on.
    """
    from boto3.s3.transfer import TransferConfig

    transfer = TransferConfig(multipart_threshold=threshold, multipart_chunksize=5 << 20)
    source, expected = random_file(size)
    fetched = source + ".down"
    try:
        with (
            s3_bucket(
                BUCKET,
                dataset=DATASET,
                owner=uploader.username,
                object_ownership="OBJECT_WRITER",
                multipart_etag=multipart_etag,
                grants=[user_grant(uploader.uid)],
            ),
            s3_service(),
        ):
            s3 = client_for(uploader.key, daemon)
            s3.upload_file(
                source,
                BUCKET,
                KEY,
                ExtraArgs={"ChecksumAlgorithm": "CRC32"},
                Config=transfer,
            )

            head = s3.head_object(Bucket=BUCKET, Key=KEY)
            assert head["ContentLength"] == size
            # The ETag says which path the bytes took: a composite is the
            # md5 of the part md5s with the part count appended; a single
            # put, or a multipart the row declined to hash, is a minted
            # UUID.
            etag = head["ETag"].strip('"')
            if parts > 1 and multipart_etag == "COMPOSITE":
                assert re.fullmatch(rf"[0-9a-f]{{32}}-{parts}", etag), etag
            else:
                assert re.fullmatch(r"[0-9a-f-]{36}", etag), etag

            s3.download_file(BUCKET, KEY, fetched, Config=transfer)
            assert md5_of(fetched) == expected

            on_disk = f"/mnt/{DATASET}/s3data/{KEY}"
            assert ssh(f"md5sum {on_disk}").split()[0] == expected
            assert call("filesystem.stat", on_disk)["uid"] == uploader.uid
            assert call("filesystem.stat", f"/mnt/{DATASET}/.truenas_s3")["uid"] == 0
    finally:
        for path in (source, fetched):
            with contextlib.suppress(FileNotFoundError):
                os.unlink(path)
