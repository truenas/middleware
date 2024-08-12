import pytest

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, password, ssh


@pytest.mark.parametrize("task", [
    {"direction": "PUSH", "also_include_naming_schema": ["auto-%Y-%m-%d-%H-%M"]},
    {"direction": "PULL", "naming_schema": ["auto-%Y-%m-%d-%H-%M"]},
])
def test_replication_sudo(task):
    with dataset("admin") as admin_homedir:
        with user({
            "username": "admin",
            "full_name": "admin",
            "group_create": True,
            "home": f"/mnt/{admin_homedir}",
            "password": "test1234",
        }):
            ssh_connection = call("keychaincredential.setup_ssh_connection", {
                "private_key": {
                    "generate_key": True,
                    "name": "test key",
                },
                "connection_name": "test",
                "setup_type": "SEMI-AUTOMATIC",
                "semi_automatic_setup": {
                    "url": "http://localhost",
                    "password": password(),
                    "username": "admin",
                    "sudo": True,
                },
            })
            try:
                with dataset("src") as src:
                    ssh(f"touch /mnt/{src}/test")
                    call("zfs.snapshot.create", {"dataset": src, "name": "auto-2023-01-18-16-00"})
                    with dataset("dst") as dst:
                        call("replication.run_onetime", {
                            **task,
                            "transport": "SSH",
                            "ssh_credentials": ssh_connection["id"],
                            "sudo": True,
                            "source_datasets": [src],
                            "target_dataset": dst,
                            "recursive": False,
                            "retention_policy": "NONE",
                        }, job=True)

                        assert ssh(f"ls /mnt/{dst}") == "test\n"
            finally:
                call("keychaincredential.delete", ssh_connection["id"])
                call("keychaincredential.delete", ssh_connection["attributes"]["private_key"])
