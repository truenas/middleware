import contextlib
import errno

import pytest

from middlewared.service_exception import CallError, ValidationError, ValidationErrors
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


def test_used_by_ignores_ssh_credentials_for_unrelated_key_pair():
    # `c` provides an SSH credential referencing its own key pair; querying a different, unrelated key pair must
    # exercise the delegate's `_is_related` check and return nothing.
    with localhost_ssh_credentials(username="root"):
        with ssh_keypair() as unrelated:
            assert call("keychaincredential.used_by", unrelated["id"]) == []


def test_used_by_ignores_sftp_cloud_credentials_for_unrelated_key_pair():
    with ssh_keypair() as used_key:
        with sftp_cloud_credential(used_key["id"]):
            with ssh_keypair() as unrelated:
                assert call("keychaincredential.used_by", unrelated["id"]) == []


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


def test_noncascade_delete_of_used_credential_raises():
    with localhost_ssh_credentials(username="root") as c:
        with pytest.raises(ValidationError) as ve:
            call("keychaincredential.delete", c["keypair"]["id"])

        assert ve.value.attribute == "options.cascade"


def test_get_of_type_nonexistent():
    with pytest.raises(CallError) as ve:
        call("keychaincredential.get_of_type", 99999999, "SSH_KEY_PAIR")

    assert ve.value.errno == errno.ENOENT


def test_get_of_type_wrong_type():
    with ssh_keypair() as keypair:
        with pytest.raises(CallError) as ve:
            call("keychaincredential.get_of_type", keypair["id"], "SSH_CREDENTIALS")

        assert ve.value.errno == errno.EINVAL


def test_get_of_type_decrypt_failure():
    with ssh_keypair() as keypair:
        # Blanking the stored attributes simulates a credential whose secret could not be decrypted.
        call("datastore.update", "system.keychaincredential", keypair["id"], {"attributes": {}})

        with pytest.raises(CallError) as ve:
            call("keychaincredential.get_of_type", keypair["id"], "SSH_KEY_PAIR")

        assert ve.value.errno == errno.EFAULT


def test_remote_ssh_host_key_scan():
    result = call("keychaincredential.remote_ssh_host_key_scan", {"host": "localhost"})

    assert result.strip()


def test_remote_ssh_host_key_scan_failure():
    with pytest.raises(CallError):
        call("keychaincredential.remote_ssh_host_key_scan", {"host": "localhost", "port": 1, "connect_timeout": 3})


def test_remote_ssh_host_key_scan_invalid_host():
    with pytest.raises(CallError):
        call("keychaincredential.remote_ssh_host_key_scan", {"host": "invalid.invalid.invalid", "connect_timeout": 3})


@pytest.fixture(scope="module")
def host_key():
    return call("keychaincredential.remote_ssh_host_key_scan", {"host": "localhost"})


def _delete_connection_and_key(connection):
    key_id = connection["attributes"]["private_key"]
    call("keychaincredential.delete", connection["id"])
    with contextlib.suppress(Exception):
        call("keychaincredential.delete", key_id)


def test_setup_ssh_connection_manual_generate_key(host_key):
    connection = call("keychaincredential.setup_ssh_connection", {
        "setup_type": "MANUAL",
        "connection_name": "keychain-manual-generate",
        "private_key": {"generate_key": True, "name": "keychain-manual-generate-key"},
        "manual_setup": {"host": "localhost", "username": "root", "remote_host_key": host_key},
    })
    try:
        assert connection["type"] == "SSH_CREDENTIALS"
        assert connection["attributes"]["host"] == "localhost"
        key_id = connection["attributes"]["private_key"]
        assert call("keychaincredential.get_instance", key_id)["name"] == "keychain-manual-generate-key"
    finally:
        _delete_connection_and_key(connection)


def test_setup_ssh_connection_manual_existing_key(host_key):
    with ssh_keypair() as keypair:
        connection = call("keychaincredential.setup_ssh_connection", {
            "setup_type": "MANUAL",
            "connection_name": "keychain-manual-existing",
            "private_key": {"generate_key": False, "existing_key_id": keypair["id"]},
            "manual_setup": {"host": "localhost", "remote_host_key": host_key},
        })
        try:
            assert connection["attributes"]["private_key"] == keypair["id"]
        finally:
            call("keychaincredential.delete", connection["id"])


def test_setup_ssh_connection_semiautomatic():
    token = call("auth.generate_token", 600, {}, False)
    connection = call("keychaincredential.setup_ssh_connection", {
        "setup_type": "SEMI-AUTOMATIC",
        "connection_name": "keychain-semi-automatic",
        "private_key": {"generate_key": True, "name": "keychain-semi-automatic-key"},
        "semi_automatic_setup": {"url": "http://localhost", "token": token},
    })
    try:
        assert connection["type"] == "SSH_CREDENTIALS"
    finally:
        _delete_connection_and_key(connection)


def test_setup_ssh_connection_rollback_removes_generated_key():
    key_name = "keychain-rollback-key"
    with pytest.raises(CallError):
        call("keychaincredential.setup_ssh_connection", {
            "setup_type": "SEMI-AUTOMATIC",
            "connection_name": "keychain-rollback",
            "private_key": {"generate_key": True, "name": key_name},
            "semi_automatic_setup": {"url": "http://localhost", "token": "invalid-token"},
        })

    assert call("keychaincredential.query", [["name", "=", key_name]]) == []


def test_setup_ssh_connection_existing_key_not_found(host_key):
    with pytest.raises(ValidationErrors) as ve:
        call("keychaincredential.setup_ssh_connection", {
            "setup_type": "MANUAL",
            "connection_name": "keychain-missing-key",
            "private_key": {"generate_key": False, "existing_key_id": 99999999},
            "manual_setup": {"host": "localhost", "remote_host_key": host_key},
        })

    assert any(e.attribute == "setup_ssh_connection.private_key.existing_key_id" for e in ve.value.errors)


def test_setup_ssh_connection_duplicate_key_name(host_key):
    with ssh_keypair() as keypair:
        existing_name = call("keychaincredential.get_instance", keypair["id"])["name"]
        with pytest.raises(ValidationErrors) as ve:
            call("keychaincredential.setup_ssh_connection", {
                "setup_type": "MANUAL",
                "connection_name": "keychain-duplicate-key-name",
                "private_key": {"generate_key": True, "name": existing_name},
                "manual_setup": {"host": "localhost", "remote_host_key": host_key},
            })

        assert any(e.attribute == "setup_ssh_connection.private_key.name" for e in ve.value.errors)


def test_setup_ssh_connection_duplicate_connection_name(host_key):
    with ssh_keypair() as keypair:
        connection = call("keychaincredential.setup_ssh_connection", {
            "setup_type": "MANUAL",
            "connection_name": "keychain-duplicate-connection",
            "private_key": {"generate_key": False, "existing_key_id": keypair["id"]},
            "manual_setup": {"host": "localhost", "remote_host_key": host_key},
        })
        try:
            with pytest.raises(ValidationErrors) as ve:
                call("keychaincredential.setup_ssh_connection", {
                    "setup_type": "MANUAL",
                    "connection_name": "keychain-duplicate-connection",
                    "private_key": {"generate_key": True, "name": "keychain-duplicate-connection-key"},
                    "manual_setup": {"host": "localhost", "remote_host_key": host_key},
                })

            assert any(e.attribute == "setup_ssh_connection.connection_name" for e in ve.value.errors)
        finally:
            call("keychaincredential.delete", connection["id"])
