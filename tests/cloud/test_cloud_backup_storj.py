import boto3
import pytest

from middlewared.test.integration.utils import call
from middlewared.test.integration.assets.cloud_backup import task
from middlewared.test.integration.assets.cloud_sync import credential
from middlewared.test.integration.assets.pool import dataset

from config import (
    STORJ_IX_AWS_ACCESS_KEY_ID,
    STORJ_IX_AWS_SECRET_ACCESS_KEY,
    STORJ_IX_BUCKET,
)


CREDENTIAL = {
    "provider": {
        "type": "STORJ_IX",
        "access_key_id": STORJ_IX_AWS_ACCESS_KEY_ID,
        "secret_access_key": STORJ_IX_AWS_SECRET_ACCESS_KEY,
    }
}


@pytest.fixture(scope="module")
def storj_credential():
    with credential(CREDENTIAL) as c:
        yield c


def test_creates_nonexistent_bucket(storj_credential):
    bucket = "nonexistentbucket"

    client = boto3.client(
        "s3",
        endpoint_url="https://gateway.storjshare.io",
        aws_access_key_id=STORJ_IX_AWS_ACCESS_KEY_ID,
        aws_secret_access_key=STORJ_IX_AWS_SECRET_ACCESS_KEY,
    )
    try:
        paginator = client.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=bucket):
            for obj in page.get("Contents", []):
                client.delete_object(Bucket=bucket, Key=obj["Key"])

        client.delete_bucket(Bucket=bucket)
    except client.exceptions.NoSuchBucket:
        pass

    assert not any(
        item["Name"] == bucket
        for item in call("cloudsync.list_buckets", storj_credential["id"])
    )

    with dataset("cloud_backup") as ds:
        with task({
            "path": f"/mnt/{ds}",
            "credentials": storj_credential["id"],
            "attributes": {
                "bucket": bucket,
                "folder": "",
            },
            "password": "test",
            "keep_last": 100,
        }):
            assert any(
                item["Name"] == bucket
                for item in call("cloudsync.list_buckets", storj_credential["id"])
            )
