from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import typing

from middlewared.api.current import SSHKeyPair as SSHKeyPairAttributes, SSHCredentials as SSHCredentialsAttributes
from middlewared.service import ValidationErrors

from .used_by import (
    KeychainCredentialUsedByDelegate,
    ReplicationTaskSSHCredentialsUsedByDelegate,
    RsyncTaskSSHCredentialsUsedByDelegate,
    SFTPCloudSyncCredentialsSSHKeyPairUsedByDelegate,
    SSHCredentialsSSHKeyPairUsedByDelegate,
)

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


class KeychainCredentialType[E]:
    name: str
    title: str

    used_by_delegates: list[type[KeychainCredentialUsedByDelegate[typing.Any]]] = []

    async def validate_and_pre_save(
        self, middleware: Middleware, verrors: ValidationErrors, schema_name: str, attributes: E,
    ) -> None:
        pass


class SyncKeychainCredentialType[E](KeychainCredentialType[E]):
    async def validate_and_pre_save(
        self, middleware: Middleware, verrors: ValidationErrors, schema_name: str, attributes: E,
    ) -> None:
        return await asyncio.to_thread(
            self.validate_and_pre_save_impl, middleware, verrors, schema_name, attributes
        )

    def validate_and_pre_save_impl(
        self, middleware: Middleware, verrors: ValidationErrors, schema_name: str, attributes: E,
    ) -> None:
        pass



class SSHKeyPair(SyncKeychainCredentialType[SSHKeyPairAttributes]):
    name = "SSH_KEY_PAIR"
    title = "SSH Key Pair"

    used_by_delegates = [
        SSHCredentialsSSHKeyPairUsedByDelegate,
        SFTPCloudSyncCredentialsSSHKeyPairUsedByDelegate,
    ]

    def validate_and_pre_save_impl(
        self, middleware: Middleware, verrors: ValidationErrors, schema_name: str, attributes: SSHKeyPairAttributes,
    ) -> None:
        if attributes.private_key:
            # TODO: It would be best if we use crypto plugin for this but as of right now we don't have support
            #  for openssh keys -
            #  `https://stackoverflow.com/questions/59029092/how-to-load-openssh-private-key-using-cryptography-python-
            #   module`
            #  so we keep on using ssh-keygen for now until that is properly supported in cryptography module.

            attributes.private_key = (attributes.private_key.strip()) + "\n"
            with tempfile.NamedTemporaryFile("w+") as f:
                os.fchmod(f.file.fileno(), 0o600)

                f.write(attributes.private_key)
                f.flush()

                proc = subprocess.run(
                    ["ssh-keygen", "-y", "-f", f.name],
                    capture_output=True, check=False, encoding="utf-8", errors="ignore",
                )
                if proc.returncode == 0:
                    public_key = proc.stdout
                else:
                    if proc.stderr.startswith("Enter passphrase:"):
                        error = "Encrypted private keys are not allowed"
                    else:
                        error = proc.stderr

                    verrors.add(f"{schema_name}.private_key", error)
                    return

            if attributes.public_key:
                if self._normalize_public_key(attributes.public_key) != self._normalize_public_key(public_key):
                    verrors.add(f"{schema_name}.public_key", "Private key and public key do not match")
            else:
                attributes.public_key = public_key

        elif not attributes.public_key:
            verrors.add(f"{schema_name}.public_key", "You must specify a key")
            return

        with tempfile.NamedTemporaryFile("w+") as f:
            os.fchmod(f.file.fileno(), 0o600)

            f.write(attributes.public_key)
            f.flush()

            proc = subprocess.run(
                ["ssh-keygen", "-l", "-f", f.name],
                capture_output=True, check=False, encoding="utf-8", errors="ignore",
            )
            if proc.returncode != 0:
                verrors.add(f"{schema_name}.public_key", "Invalid public key")
                return

    def _normalize_public_key(self, public_key: str) -> str:
        return " ".join(public_key.split()[:2]).strip()


class SSHCredentials(KeychainCredentialType[SSHCredentialsAttributes]):
    name = "SSH_CREDENTIALS"
    title = "SSH credentials"

    used_by_delegates = [
        ReplicationTaskSSHCredentialsUsedByDelegate,
        RsyncTaskSSHCredentialsUsedByDelegate,
    ]


_TYPE_CLASSES: list[type[KeychainCredentialType[typing.Any]]] = [SSHKeyPair, SSHCredentials]
TYPES: dict[str, KeychainCredentialType[typing.Any]] = {type_.name: type_() for type_ in _TYPE_CLASSES}
