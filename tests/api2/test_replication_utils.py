import pytest

from middlewared.test.integration.utils import call, pool


@pytest.fixture(scope="module")
def localhost_ssh_connection():
    credential = call("keychaincredential.create", {
        "name": "key",
        "type": "SSH_KEY_PAIR",
        "attributes": call("keychaincredential.generate_ssh_key_pair"),
    })
    try:
        token = call("auth.generate_token", 600, {}, False)
        connection = call("keychaincredential.remote_ssh_semiautomatic_setup", {
            "name": "localhost",
            "url": "http://localhost",
            "token": token,
            "private_key": credential["id"],
        })
        try:
            yield connection["id"]
        finally:
            call("keychaincredential.delete", connection["id"])
    finally:
        call("keychaincredential.delete", credential["id"])


@pytest.mark.parametrize("transport", ["SSH", "SSH+NETCAT"])
def test_list_datasets_ssh(localhost_ssh_connection, transport):
    assert pool in call("replication.list_datasets", transport, localhost_ssh_connection)


def test_replication_pair():
    public_key = call("keychaincredential.generate_ssh_key_pair")["public_key"]

    result = call("replication.pair", {
        "hostname": "127.0.0.1",
        "public-key": public_key,
        "user": "root",
    })

    assert result["ssh_port"] == call("ssh.config")["tcpport"]
    assert "127.0.0.1 ssh-" in result["ssh_hostkey"]
