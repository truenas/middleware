import contextlib

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.s3 import s3_server
from middlewared.test.integration.utils import call


@contextlib.contextmanager
def credential(data):
    data = {
        "name": "Test",
        **data,
    }

    credential = call("cloudsync.credentials.create", data)

    try:
        yield credential
    finally:
        call("cloudsync.credentials.delete", credential["id"])


@contextlib.contextmanager
def task(data):
    data = {
        "description": "Test",
        "schedule": {
            "minute": "00",
            "hour": "00",
            "dom": "1",
            "month": "1",
            "dow": "1",
        },
        **data
    }

    task = call("cloudsync.create", data)

    try:
        yield task
    finally:
        call("cloudsync.delete", task["id"])


@contextlib.contextmanager
def local_s3_credential(credential_params=None):
    credential_params = credential_params or {}

    with dataset("cloudsync_remote") as remote_dataset:
        with s3_server(remote_dataset) as s3:
            with credential({
                "provider": "S3",
                "attributes": {
                    "access_key_id": s3.access_key,
                    "secret_access_key": s3.secret_key,
                    "endpoint": "http://localhost:9000",
                    "skip_region": True,
                    **credential_params,
                },
            }) as c:
                yield c


@contextlib.contextmanager
def local_s3_task(params=None, credential_params=None):
    params = params or {}
    credential_params = credential_params or {}

    with dataset("cloudsync_local") as local_dataset:
        with local_s3_credential(credential_params) as c:
            with task({
                "direction": "PUSH",
                "transfer_mode": "COPY",
                "path": f"/mnt/{local_dataset}",
                "credentials": c["id"],
                "attributes": {
                    "bucket": "bucket",
                    "folder": "",
                },
                **params,
            }) as t:
                yield t
