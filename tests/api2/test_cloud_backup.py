import boto3
import pytest

from middlewared.client import ClientException
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.cloud_backup import task, run_task
from middlewared.test.integration.assets.cloud_sync import credential
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils.call import call
from middlewared.test.integration.utils.mock import mock
from middlewared.test.integration.utils.ssh import ssh

try:
    from config import (
        AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY,
        AWS_BUCKET,
    )
    pytestmark = pytest.mark.cloudsync
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


@pytest.fixture(scope="module")
def zvol():
    with dataset("cloud_backup", {"type": "VOLUME", "volsize": 1024 * 1024}) as zvol:
        path = f"/dev/zvol/{zvol}"
        ssh(f"dd if=/dev/urandom of={path} bs=1M count=1")

        yield path


def test_zvol_cloud_backup(s3_credential, zvol):
    clean()

    with mock("cloud_backup.validate_zvol", return_value=None):
        with task({
            "path": zvol,
            "credentials": s3_credential["id"],
            "attributes": {
                "bucket": AWS_BUCKET,
                "folder": "cloud_backup",
            },
            "password": "test",
        }) as t:
            call("cloud_backup.init", t["id"], job=True)

            run_task(t)


def test_zvol_cloud_backup_create_time_validation(s3_credential, zvol):
    clean()

    with pytest.raises(ValidationErrors) as ve:
        with task({
            "path": zvol,
            "credentials": s3_credential["id"],
            "attributes": {
                "bucket": AWS_BUCKET,
                "folder": "cloud_backup",
            },
            "password": "test",
        }):
            pass

    assert "cloud_backup_create.path" in ve.value


def test_zvol_cloud_backup_runtime_validation(s3_credential, zvol):
    clean()

    m = mock("cloud_backup.validate_zvol", return_value=None)
    m.__enter__()
    exited = False
    try:
        with task({
            "path": zvol,
            "credentials": s3_credential["id"],
            "attributes": {
                "bucket": AWS_BUCKET,
                "folder": "cloud_backup",
            },
            "password": "test",
        }) as t:
            m.__exit__(None, None, None)
            exited = True

            with pytest.raises(ClientException):
                run_task(t)
    finally:
        if not exited:
            m.__exit__(None, None, None)
