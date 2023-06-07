import contextlib

from middlewared.test.integration.utils import call


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

    task = call("cloud_backup.create", data)

    try:
        yield task
    finally:
        call("cloud_backup.delete", task["id"])


def run_task(task, timeout=120):
    call("cloud_backup.sync", task["id"], job=True, timeout=timeout)
