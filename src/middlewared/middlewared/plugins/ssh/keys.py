from __future__ import annotations

import base64
import enum
import os
import subprocess
import typing

if typing.TYPE_CHECKING:
    from middlewared.service import ServiceContext


class SSHHostKey(enum.Enum):
    SSH_HOST_KEY = "ssh_host_key"
    SSH_HOST_KEY_PUB = "ssh_host_key.pub"
    SSH_HOST_DSA_KEY = "ssh_host_dsa_key"
    SSH_HOST_DSA_KEY_PUB = "ssh_host_dsa_key.pub"
    SSH_HOST_DSA_KEY_CERT_PUB = "ssh_host_dsa_key-cert.pub"
    SSH_HOST_ECDSA_KEY = "ssh_host_ecdsa_key"
    SSH_HOST_ECDSA_KEY_PUB = "ssh_host_ecdsa_key.pub"
    SSH_HOST_ECDSA_KEY_CERT_PUB = "ssh_host_ecdsa_key-cert.pub"
    SSH_HOST_RSA_KEY = "ssh_host_rsa_key"
    SSH_HOST_RSA_KEY_PUB = "ssh_host_rsa_key.pub"
    SSH_HOST_RSA_KEY_CERT_PUB = "ssh_host_rsa_key-cert.pub"
    SSH_HOST_ED25519_KEY = "ssh_host_ed25519_key"
    SSH_HOST_ED25519_KEY_PUB = "ssh_host_ed25519_key.pub"
    SSH_HOST_ED25519_KEY_CERT_PUB = "ssh_host_ed25519_key-cert.pub"

    @property
    def path(self) -> str:
        return os.path.join("/etc/ssh", self.value)

    @property
    def column(self) -> str:
        return self.name.lower()


def cleanup_host_keys(context: ServiceContext) -> None:
    config = context.middleware.call_sync("datastore.config", "services.ssh")
    for key in SSHHostKey:
        if config[key.column]:
            continue
        try:
            os.unlink(key.path)
        except FileNotFoundError:
            continue
        context.middleware.logger.warning("Removing irrelevant SSH host key %r", key.path)


def generate_host_keys(context: ServiceContext) -> None:
    context.middleware.logger.debug("Generating SSH host keys")
    p = subprocess.run(
        # For each of the key types (rsa, dsa, ecdsa and ed25519) for which host keys do not exist,
        # generate the host keys with the default key file path, an empty passphrase, default bits
        # for the key type, and default comment.
        ["ssh-keygen", "-A"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="ignore",
    )
    if p.returncode != 0:
        context.middleware.logger.error("Error generating SSH host keys: %s", p.stdout)


def save_host_keys(context: ServiceContext) -> None:
    update = {}
    old = context.middleware.call_sync("datastore.query", "services_ssh", [], {"get": True})
    for key in SSHHostKey:
        try:
            with open(key.path, "rb") as f:
                data = base64.b64encode(f.read()).decode("ascii")
        except FileNotFoundError:
            continue

        if data != old[key.column]:
            update[key.column] = data

    if update:
        context.middleware.call_sync("datastore.update", "services.ssh", old["id"], update, {"ha_sync": False})
