import pytest

from middlewared.test.integration.assets.keychain import localhost_ssh_credentials
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh


def test_keychain_credential_update_reloads_zettarepl():
    # Updating a keychain credential must call `zettarepl.update_tasks` so that running replication tasks pick up the
    # new credential. We verify this by breaking (and then restoring) the SSH key pair backing a replication task.
    with localhost_ssh_credentials(username="root") as c:
        keypair = c["keypair"]
        original_attributes = keypair["attributes"]

        with dataset("keychain_repl_src") as src, dataset("keychain_repl_dst") as dst:
            task = call(
                "replication.create",
                {
                    "name": "keychain-zettarepl",
                    "direction": "PUSH",
                    "transport": "SSH",
                    "ssh_credentials": c["credentials"]["id"],
                    "source_datasets": [src],
                    "target_dataset": dst,
                    "recursive": False,
                    "auto": False,
                    "retention_policy": "NONE",
                    "also_include_naming_schema": ["auto-%Y-%m-%d-%H-%M"],
                },
            )
            try:
                # Valid key pair -> replication succeeds
                ssh(f"touch /mnt/{src}/test1")
                call(
                    "pool.snapshot.create",
                    {"dataset": src, "name": "auto-2024-01-01-00-00"},
                )
                call("replication.run", task["id"], job=True)
                assert "test1" in ssh(f"ls /mnt/{dst}")

                # Break the key pair; `do_update` must reload zettarepl so the task now uses the (wrong) key
                call(
                    "keychaincredential.update",
                    keypair["id"],
                    {
                        "attributes": call("keychaincredential.generate_ssh_key_pair"),
                    },
                )
                ssh(f"touch /mnt/{src}/test2")
                call(
                    "pool.snapshot.create",
                    {"dataset": src, "name": "auto-2024-01-02-00-00"},
                )
                with pytest.raises(Exception):
                    call("replication.run", task["id"], job=True)

                # Restore the key pair -> zettarepl reloaded again, replication succeeds
                call(
                    "keychaincredential.update",
                    keypair["id"],
                    {"attributes": original_attributes},
                )
                call("replication.run", task["id"], job=True)
                assert "test2" in ssh(f"ls /mnt/{dst}")
            finally:
                call("replication.delete", task["id"])
