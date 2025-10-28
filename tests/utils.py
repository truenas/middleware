import contextlib
from time import sleep

from middlewared.test.integration.utils import call


@contextlib.contextmanager
def create_dataset(dataset: str, options: dict | None = None, acl: dict | None = None, mode: str | None = None):
    ds_id = call("pool.dataset.create", {"name": dataset, **(options or {})})["id"]

    if mode is not None:
        call("filesystem.setperm", {"path": f"/mnt/{dataset}", "mode": mode}, job=True, timeout=180)
    elif acl is not None:
        call("filesystem.setacl", {"path": f"/mnt/{dataset}", "dacl": acl}, job=True, timeout=180)

    try:
        yield dataset
    finally:
        # dataset may be busy
        sleep(5)
        call("pool.dataset.delete", ds_id, {"recursive": True})
