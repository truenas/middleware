import os
import subprocess
import tempfile

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.utils import call


def _generate_private_key(passphrase=""):
    with tempfile.TemporaryDirectory() as tmpdir:
        key = os.path.join(tmpdir, "key")
        subprocess.run(["ssh-keygen", "-t", "rsa", "-f", key, "-N", passphrase, "-q"], check=True)
        with open(key) as f:
            return f.read()


def _create_key_pair(attributes):
    return call("keychaincredential.create", {
        "name": "keychain-key-pair-test",
        "type": "SSH_KEY_PAIR",
        "attributes": attributes,
    })


def _assert_error(ve, attribute, message):
    assert any(e.attribute == attribute and message in e.errmsg for e in ve.value.errors), ve.value.errors


def test_create_key_pair_with_passphrase():
    with pytest.raises(ValidationErrors) as ve:
        _create_key_pair({"private_key": _generate_private_key("passphrase")})

    _assert_error(ve, "keychain_credential_create.attributes.private_key", "Encrypted private keys are not allowed")


def test_create_key_pair_with_broken_private_key():
    with pytest.raises(ValidationErrors) as ve:
        _create_key_pair({
            "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\nbroken\n-----END OPENSSH PRIVATE KEY-----\n",
        })

    assert any(
        e.attribute == "keychain_credential_create.attributes.private_key" for e in ve.value.errors
    ), ve.value.errors


def test_create_key_pair_without_keys():
    with pytest.raises(ValidationErrors) as ve:
        _create_key_pair({})

    _assert_error(ve, "keychain_credential_create.attributes.public_key", "You must specify a key")


def test_create_key_pair_with_non_matching_keys():
    pair1 = call("keychaincredential.generate_ssh_key_pair")
    pair2 = call("keychaincredential.generate_ssh_key_pair")

    with pytest.raises(ValidationErrors) as ve:
        _create_key_pair({"private_key": pair1["private_key"], "public_key": pair2["public_key"]})

    _assert_error(
        ve, "keychain_credential_create.attributes.public_key", "Private key and public key do not match"
    )


def test_create_key_pair_with_invalid_public_key_only():
    with pytest.raises(ValidationErrors) as ve:
        _create_key_pair({"public_key": "this is not a valid public key"})

    _assert_error(ve, "keychain_credential_create.attributes.public_key", "Invalid public key")


def test_create_key_pair_derives_public_key_from_private_key():
    generated = call("keychaincredential.generate_ssh_key_pair")

    keypair = _create_key_pair({"private_key": generated["private_key"]})
    try:
        # The public key is not supplied, so it must be derived from the private key. Compare the key material
        # (second field) because the derived key carries no comment.
        assert keypair["attributes"]["public_key"].split()[1] == generated["public_key"].split()[1]
    finally:
        call("keychaincredential.delete", keypair["id"])
