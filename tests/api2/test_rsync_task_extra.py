import contextlib

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call


EXTRA = [r"--rsync-path=sudo\ /usr/bin/rsync", "--exclude=.snapshot"]


@contextlib.contextmanager
def rsync_task(path, extra):
    task = call(
        "rsynctask.create",
        {
            "path": path,
            "user": "root",
            "mode": "MODULE",
            "remotehost": "127.0.0.1",
            "remotemodule": "test",
            "extra": extra,
        },
    )
    try:
        yield task
    finally:
        call("rsynctask.delete", task["id"])


@pytest.fixture(scope="module")
def task():
    with dataset("rsync_extra") as ds:
        with rsync_task(f"/mnt/{ds}", EXTRA) as t:
            yield t


def test_extra_survives_a_round_trip(task):
    """Reading a task back does not split a parameter the user grouped."""
    assert call("rsynctask.get_instance", task["id"])["extra"] == EXTRA


def test_extra_survives_an_unrelated_update(task):
    """Saving the edit screen used to join the list and split it again."""
    call("rsynctask.update", task["id"], {"desc": "edited"})

    assert call("rsynctask.get_instance", task["id"])["extra"] == EXTRA


def test_unbalanced_quotes_name_the_parameter(task):
    """Validation reads one parameter at a time, so the error gives its index."""
    with pytest.raises(ValidationErrors) as ve:
        call("rsynctask.update", task["id"], {"extra": ["-avz", '--rsync-path="sudo rsync']})

    assert ve.value.errors[0].attribute == "rsync_task_update.extra.1"
