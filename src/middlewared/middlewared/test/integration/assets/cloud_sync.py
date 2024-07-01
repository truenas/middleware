import contextlib

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.ftp import anonymous_ftp_server
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
def local_ftp_credential_data():
    with anonymous_ftp_server(dataset_name="cloudsync_remote") as ftp:
        yield {
            "provider": "FTP",
            "attributes": {
                "host": "localhost",
                "port": 21,
                "user": ftp.username,
                "pass": ftp.password,
            },
        }


@contextlib.contextmanager
def local_ftp_credential():
    with local_ftp_credential_data() as data:
        with credential(data) as c:
            yield c


@contextlib.contextmanager
def local_ftp_task(params=None):
    params = params or {}

    with dataset("cloudsync_local") as local_dataset:
        with local_ftp_credential() as c:
            with task({
                "direction": "PUSH",
                "transfer_mode": "COPY",
                "path": f"/mnt/{local_dataset}",
                "credentials": c["id"],
                "attributes": {
                    "folder": "",
                },
                **params,
            }) as t:
                yield t


def run_task(task, timeout=120):
    call("cloudsync.sync", task["id"], job=True, timeout=timeout)
