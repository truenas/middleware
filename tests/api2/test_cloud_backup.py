import boto3
import pytest

from middlewared.client import ClientException
from middlewared.test.integration.assets.cloud_backup import task, run_task
from middlewared.test.integration.assets.cloud_sync import credential
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils.call import call
from middlewared.test.integration.utils.ssh import ssh

try:
    from config import (
        AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY,
        AWS_BUCKET,
    )
except ImportError:
    pytestmark = pytest.mark.skip(reason="AWS credential are missing in config.py")


def clean():
    s3 = boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    ).resource("s3")
    bucket = s3.Bucket(AWS_BUCKET)
    bucket.objects.filter(Prefix="cloud_backup/").delete()


@pytest.fixture(scope="module")
def s3_credential():
    with credential({
        "provider": "S3",
        "attributes": {
            "access_key_id": AWS_ACCESS_KEY_ID,
            "secret_access_key": AWS_SECRET_ACCESS_KEY,
        },
    }) as c:
        yield c


def test_cloud_backup(s3_credential):
    clean()

    with dataset("cloud_backup") as local_dataset:
        ssh(f"dd if=/dev/urandom of=/mnt/{local_dataset}/blob1 bs=1M count=1")

        with task({
            "path": f"/mnt/{local_dataset}",
            "credentials": s3_credential["id"],
            "attributes": {
                "bucket": AWS_BUCKET,
                "folder": "cloud_backup",
            },
            "password": "test",
        }) as t:
            call("cloud_backup.init", t["id"], job=True)

            run_task(t)

            logs = ssh("cat " + call("cloud_backup.get_instance", t["id"])["job"]["logs_path"])
            assert "Files:           1 new,     0 changed,     0 unmodified" in logs

            ssh(f"dd if=/dev/urandom of=/mnt/{local_dataset}/blob2 bs=1M count=1")

            run_task(t)

            logs = ssh("cat " + call("cloud_backup.get_instance", t["id"])["job"]["logs_path"])
            assert "Files:           1 new,     0 changed,     1 unmodified" in logs


def test_double_init_error(s3_credential):
    clean()

    with dataset("cloud_backup") as local_dataset:
        with task({
            "path": f"/mnt/{local_dataset}",
            "credentials": s3_credential["id"],
            "attributes": {
                "bucket": AWS_BUCKET,
                "folder": "cloud_backup",
            },
            "password": "test",
        }) as t:
            call("cloud_backup.init", t["id"], job=True)

            with pytest.raises(ClientException) as ve:
                call("cloud_backup.init", t["id"], job=True)

            assert ve.value.error.rstrip().endswith("already initialized")
