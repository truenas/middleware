import pytest

from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.assets.pool import pool

pytestmark = pytest.mark.zfs


def test_pool_dataset_unlock_recursive():
    key = "0" * 32
    try:
        ssh(f"echo -n '{key}' > /tmp/key")
        ssh(f"zfs create -o encryption=on -o keyformat=raw -o keylocation=file:///tmp/key {pool}/test")
        ssh(f"zfs create -o encryption=on -o keyformat=raw -o keylocation=file:///tmp/key {pool}/test/nested")
        ssh(f"echo TEST > /mnt/{pool}/test/nested/file")
        ssh("rm /tmp/key")
        ssh(f"zfs set readonly=on {pool}/test")
        ssh(f"zfs set readonly=on {pool}/test/nested")
        ssh(f"zfs unmount {pool}/test")
        ssh(f"zfs unload-key -r {pool}/test")

        result = call("pool.dataset.unlock", f"{pool}/test", {
            "recursive": True,
            "datasets": [
                {
                    "name": f"{pool}/test",
                    "key": key.encode("ascii").hex(),
                    "recursive": True,
                },
            ],
        }, job=True)
        assert not result["failed"]

        assert not call("pool.dataset.get_instance", f"{pool}/test")["locked"]
        assert not call("pool.dataset.get_instance", f"{pool}/test/nested")["locked"]

        # Ensure the child dataset is mounted
        assert ssh(f"cat /mnt/{pool}/test/nested/file") == "TEST\n"

        # Ensure the keys are stored in the database to be able to unlock the datasets after reboot
        assert call("datastore.query", "storage.encrypteddataset", [["name", "=", f"{pool}/test"]])
        assert call("datastore.query", "storage.encrypteddataset", [["name", "=", f"{pool}/test/nested"]])
    finally:
        call("pool.dataset.delete", f"{pool}/test", {"recursive": True})
