import contextlib

from middlewared.test.integration.assets.cloud_sync import credential as cloud_credential
from middlewared.test.integration.assets.keychain import localhost_ssh_credentials, ssh_keypair
from middlewared.test.integration.assets.replication import replication_task
from middlewared.test.integration.utils import call


def _replication_data(ssh_credentials_id):
    return {
        "name": "keychain-used-by-test",
        "direction": "PUSH",
        "transport": "SSH",
        "ssh_credentials": ssh_credentials_id,
        "source_datasets": ["source"],
        "target_dataset": "target",
        "recursive": False,
        "name_regex": ".+",
        "auto": False,
        "retention_policy": "NONE",
    }


@contextlib.contextmanager
def sftp_cloud_credential(private_key_id):
    with cloud_credential({
        "name": "keychain-used-by-sftp",
        "provider": {
            "type": "SFTP",
            "host": "localhost",
            "user": "root",
            "private_key": private_key_id,
        },
    }) as c:
        yield c


def test_used_by_empty_for_unused_key_pair():
    with ssh_keypair() as keypair:
        assert call("keychaincredential.used_by", keypair["id"]) == []


def test_ssh_key_pair_used_by_ssh_credentials():
    with localhost_ssh_credentials(username="root") as c:
        used_by = call("keychaincredential.used_by", c["keypair"]["id"])
        assert {
            "title": f"SSH credentials {c['credentials']['name']}",
            "unbind_method": "delete",
        } in used_by


def test_ssh_key_pair_used_by_sftp_cloud_credentials():
    with ssh_keypair() as keypair:
        with sftp_cloud_credential(keypair["id"]) as cred:
            used_by = call("keychaincredential.used_by", keypair["id"])
            assert {
                "title": f"Cloud credentials {cred['name']}",
                "unbind_method": "disable",
            } in used_by


def test_ssh_credentials_used_by_replication_task():
    with localhost_ssh_credentials(username="root") as c:
        with replication_task(_replication_data(c["credentials"]["id"])) as task:
            used_by = call("keychaincredential.used_by", c["credentials"]["id"])
            assert {
                "title": f"Replication task {task['name']}",
                "unbind_method": "disable",
            } in used_by


def test_ssh_key_pair_used_by_is_recursive():
    # Deleting the key pair cascades into the SSH credentials that reference it, which in turn are used by the
    # replication task, so ``used_by`` for the key pair must report both objects.
    with localhost_ssh_credentials(username="root") as c:
        with replication_task(_replication_data(c["credentials"]["id"])) as task:
            used_by = call("keychaincredential.used_by", c["keypair"]["id"])
            assert {
                "title": f"SSH credentials {c['credentials']['name']}",
                "unbind_method": "delete",
            } in used_by
            assert {
                "title": f"Replication task {task['name']}",
                "unbind_method": "disable",
            } in used_by


def test_cascade_delete_disables_replication_task():
    with localhost_ssh_credentials(username="root") as c:
        with replication_task(_replication_data(c["credentials"]["id"])) as task:
            call("keychaincredential.delete", c["credentials"]["id"], {"cascade": True})

            task = call("replication.get_instance", task["id"])
            assert not task["enabled"]
            assert task["ssh_credentials"] is None


def test_cascade_delete_ssh_key_pair_deletes_ssh_credentials():
    # SSH credentials that reference a key pair are unbound with the DELETE method, so cascade-deleting the key pair
    # deletes the SSH credentials that use it as well.
    with localhost_ssh_credentials(username="root") as c:
        call("keychaincredential.delete", c["keypair"]["id"], {"cascade": True})

        assert call("keychaincredential.query", [["id", "=", c["credentials"]["id"]]]) == []


def test_cascade_delete_unbinds_sftp_cloud_credentials():
    with ssh_keypair() as keypair:
        with sftp_cloud_credential(keypair["id"]) as cred:
            call("keychaincredential.delete", keypair["id"], {"cascade": True})

            cred = call("cloudsync.credentials.get_instance", cred["id"])
            assert cred["provider"].get("private_key") is None
