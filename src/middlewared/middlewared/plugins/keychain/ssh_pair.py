from __future__ import annotations

import base64
import errno
import os
import re
import ssl
from typing import cast
import urllib.parse

from pydantic import Secret
from truenas_api_client import Client
from truenas_api_client.exc import ClientException

from middlewared.api.base import BaseModel, LongString, NonEmptyString, convert_model
from middlewared.api.current import (
    KeychainCredentialCreateSSHCredentialsEntry,
    KeychainCredentialCreateSSHKeyPairEntry,
    KeychainCredentialRemoteSSHSemiautomaticSetup,
    QueryOptions,
    SetupSSHConnectionManual,
    SetupSSHConnectionSemiautomatic,
    SSHCredentials,
    SSHCredentialsEntry,
    SSHKeyPairEntry,
)
from middlewared.plugins.account_.constants import NO_LOGIN_SHELL
from middlewared.service import ServiceContext, ValidationErrors
from middlewared.service_exception import CallError, MatchNotFound

from .ssh_key import process_ssh_keyscan_output


class KeychainCredentialSSHPairArg(BaseModel):
    remote_hostname: NonEmptyString
    username: str = "root"
    public_key: LongString


class KeychainCredentialSSHPairArgs(BaseModel):
    data: KeychainCredentialSSHPairArg


class KeychainCredentialSSHPairResultData(BaseModel):
    port: int
    host_key: LongString


class KeychainCredentialSSHPairResult(BaseModel):
    result: KeychainCredentialSSHPairResultData


def ssh_pair(context: ServiceContext, data: KeychainCredentialSSHPairArg) -> KeychainCredentialSSHPairResultData:
    service = context.call_sync2(context.s.service.query, [("service", "=", "ssh")], QueryOptions(get=True))
    ssh = context.call_sync2(context.s.ssh.config)
    try:
        user = context.middleware.call_sync(
            "user.query",
            [("username", "=", data.username), ("local", "=", True)],
            {"get": True}
        )
    except MatchNotFound:
        raise CallError(f"User {data.username} does not exist")

    if user["home"].startswith("/var/empty") or not os.path.exists(user["home"]):
        raise CallError(f"Home directory {user['home']} does not exist", errno.ENOENT)

    # Make sure SSH is enabled
    if not service.enable:
        context.call_sync2(context.s.service.update, "ssh", {"enable": True})

    if service.state != "RUNNING":
        context.call_sync2(context.s.service.control, "START", "ssh").wait_sync(raise_error=True)

        # This might be the first time of the service being enabled
        # which will then result in new host keys we need to grab
        ssh = context.call_sync2(context.middleware.services.ssh.config)

    if not ssh.host_rsa_key_pub:
        raise CallError("Host RSA key not configured")

    if not ssh.host_ecdsa_key_pub:
        raise CallError("Host ECDSA key not configured")

    if not ssh.host_ed25519_key_pub:
        raise CallError("Host ED25519 key not configured")

    # Write public key in user authorized_keys for SSH
    pubkey = (user["sshpubkey"] or "").strip()
    if data.public_key not in pubkey:
        pubkey += "\n" + data.public_key + "\n"
        context.middleware.call_sync("user.update", user["id"], {"sshpubkey": pubkey})

    ssh_hostkey = "{0} {1}\n{0} {2}\n{0} {3}\n".format(
        data.remote_hostname,
        base64.b64decode(ssh.host_rsa_key_pub.encode()).decode(),
        base64.b64decode(ssh.host_ecdsa_key_pub.encode()).decode(),
        base64.b64decode(ssh.host_ed25519_key_pub.encode()).decode(),
    )

    return KeychainCredentialSSHPairResultData(
        port=ssh.tcpport,
        host_key=ssh_hostkey,
    )


def get_ssh_key_pair_with_private_key(context: ServiceContext, id_: int) -> SSHKeyPairEntry | None:
    try:
        credential = context.call_sync2(context.s.keychaincredential.query, [["id", "=", id_]], QueryOptions(get=True))
    except MatchNotFound:
        return None

    if credential.type != "SSH_KEY_PAIR":
        return None

    ssh_keypair = cast(SSHKeyPairEntry, credential)

    if not ssh_keypair.attributes.get_secret_value().private_key:
        return None

    return ssh_keypair


def remote_ssh_semiautomatic_setup(
    context: ServiceContext, data: KeychainCredentialRemoteSSHSemiautomaticSetup,
) -> SSHCredentialsEntry:
    replication_key = get_ssh_key_pair_with_private_key(context, data.private_key.get_secret_value())
    if replication_key is None:
        raise CallError("Specified key pair not found")

    try:
        client = Client(os.path.join(re.sub("^http", "ws", data.url), "websocket"),
                        verify_ssl=data.verify_ssl)
    except ssl.SSLCertVerificationError as e:
        raise CallError(str(e), CallError.ESSLCERTVERIFICATIONERROR)
    except Exception as e:
        raise CallError(f"Unable to connect to remote system: {e}")

    with client as c:
        if data.token.get_secret_value():
            if not c.call("auth.login_with_token", data.token.get_secret_value()):
                raise CallError("Invalid token")
        elif data.password.get_secret_value():
            try:
                c.login_with_password(data.admin_username, data.password.get_secret_value(),
                                      otp_token=data.otp_token.get_secret_value() or None)
            except ValueError as e:
                # login_with_password raises ValueError with a descriptive message for:
                # invalid credentials, OTP required / invalid OTP, expired account,
                # account lacks API access, or HA redirect to active controller.
                raise CallError(str(e))
        else:
            raise CallError("You should specify either remote system password or temporary authentication token")

        try:
            response = c.call("keychaincredential.ssh_pair", {
                "remote_hostname": "any-host",
                "username": data.username,
                "public_key": replication_key.attributes.get_secret_value().public_key,
            })
        except ClientException as e:
            raise CallError(
                f"Semi-automatic SSH connection setup failed: {e}\n\n"
                f"Please make sure that home directory for {data.username} user on the remote system exists and "
                "is writeable."
            )
        except Exception as e:
            raise CallError(f"Semi-automatic SSH connection setup failed: {e!r}")

        user = c.call("user.query", [["username", "=", data.username], ['local', '=', True]], {"get": True})
        user_update = {}
        if user["shell"] == NO_LOGIN_SHELL:
            user_update["shell"] = "/usr/bin/bash"
        if data.sudo:
            if "ALL" not in user["sudo_commands_nopasswd"]:
                zfs_binary = "/usr/sbin/zfs"
                if zfs_binary not in user["sudo_commands_nopasswd"]:
                    user_update["sudo_commands_nopasswd"] = user["sudo_commands_nopasswd"] + [zfs_binary]
        try:
            c.call("user.update", user["id"], user_update)
        except Exception as e:
            raise CallError(f"Error updating remote user attributes: {e}")

    return convert_model(context.call_sync2(
        context.s.keychaincredential.do_create,
        KeychainCredentialCreateSSHCredentialsEntry(
            name=data.name,
            type="SSH_CREDENTIALS",
            attributes=Secret(SSHCredentials(
                host=urllib.parse.urlparse(data.url).hostname or "",
                port=response["port"],
                username=data.username,
                private_key=replication_key.id,
                remote_host_key=process_ssh_keyscan_output(response["host_key"]),
                connect_timeout=data.connect_timeout,
            )),
        )
    ), SSHCredentialsEntry)


async def _validate_options(
    context: ServiceContext, options: SetupSSHConnectionManual | SetupSSHConnectionSemiautomatic,
) -> None:
    """
    If `generate_key` is set, ensure that no key with the given name already exists.
    Otherwise, ensure that a key with the given `existing_key_id` does exist.

    Also ensure that a key with the name `connection_name` does not exist yet.
    """
    pkey_config_ = options.private_key
    schema_name = 'setup_ssh_connection'
    verrors = ValidationErrors()

    if pkey_config_.generate_key:
        if await context.call2(context.s.keychaincredential.query, [['name', '=', pkey_config_.name]]):
            verrors.add(f'{schema_name}.private_key.name', 'Is already in use by another SSH Key pair')

    elif not await context.call2(
        context.s.keychaincredential.query,
        [['id', '=', pkey_config_.existing_key_id]]
    ):
        verrors.add(f'{schema_name}.private_key.existing_key_id', 'SSH Key Pair not found')

    if await context.call2(context.s.keychaincredential.query, [['name', '=', options.connection_name]]):
        verrors.add(f'{schema_name}.connection_name', 'Is already in use by another Keychain Credential')

    verrors.check()


async def setup_ssh_connection(
    context: ServiceContext, options: SetupSSHConnectionManual | SetupSSHConnectionSemiautomatic,
) -> SSHCredentialsEntry:
    await _validate_options(context, options)

    pkey_config_ = options.private_key

    # We are going to generate an SSH Key pair now if required
    if pkey_config_.generate_key:
        key_config = await context.call2(context.s.keychaincredential.generate_ssh_key_pair)
        ssh_key_pair = await context.call2(
            context.s.keychaincredential.do_create,
            KeychainCredentialCreateSSHKeyPairEntry(
                name=pkey_config_.name,
                type='SSH_KEY_PAIR',
                attributes=Secret(key_config),
            ),
        )
    else:
        ssh_key_pair = await context.call2(
            context.s.keychaincredential.get_of_type,
            pkey_config_.existing_key_id,
            'SSH_KEY_PAIR',
        )

    try:
        if options.setup_type == 'SEMI-AUTOMATIC':
            resp = await context.call2(
                context.s.keychaincredential.remote_ssh_semiautomatic_setup,
                KeychainCredentialRemoteSSHSemiautomaticSetup(
                    **options.semi_automatic_setup.model_dump(context={"expose_secrets": True}),
                    private_key=Secret(ssh_key_pair.id),
                    name=options.connection_name,
                )
            )
        else:
            resp = await context.call2(  # type: ignore[assignment]
                context.s.keychaincredential.do_create,
                KeychainCredentialCreateSSHCredentialsEntry(
                    type='SSH_CREDENTIALS',
                    name=options.connection_name,
                    attributes=Secret(SSHCredentials(
                        **options.manual_setup.model_dump(),
                        private_key=ssh_key_pair.id,
                    )),
                )
            )
    except Exception:
        if pkey_config_.generate_key:
            await context.call2(context.s.keychaincredential.delete, ssh_key_pair.id)
        raise
    else:
        return convert_model(resp, SSHCredentialsEntry)
