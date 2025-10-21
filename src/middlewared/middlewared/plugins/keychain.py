import asyncio
import base64
import enum
import errno
import os
import re
import ssl
import subprocess
import tempfile
from typing import Literal
import urllib.parse

from truenas_api_client import Client, ClientException

from middlewared.api import api_method
from middlewared.api.base import BaseModel, LongString, NonEmptyString, single_argument_args, single_argument_result
from middlewared.api.current import (
    KeychainCredentialEntry,
    SSHKeyPairEntry, SSHCredentialsEntry,
    KeychainCredentialCreateArgs, KeychainCredentialCreateResult,
    KeychainCredentialUpdateArgs, KeychainCredentialUpdateResult,
    KeychainCredentialDeleteArgs, KeychainCredentialDeleteResult,
    KeychainCredentialUsedByArgs, KeychainCredentialUsedByResult,
    KeychainCredentialGenerateSshKeyPairArgs, KeychainCredentialGenerateSshKeyPairResult,
    KeychainCredentialRemoteSshHostKeyScanArgs, KeychainCredentialRemoteSshHostKeyScanResult,
    KeychainCredentialRemoteSshSemiautomaticSetupArgs, KeychainCredentialRemoteSshSemiautomaticSetupResult,
)
from middlewared.plugins.account_.constants import NO_LOGIN_SHELL
from middlewared.service_exception import CallError, MatchNotFound, ValidationError, ValidationErrors
from middlewared.service import CRUDService, private
import middlewared.sqlalchemy as sa
from middlewared.utils import run


class KeychainCredentialType:
    name = NotImplemented
    title = NotImplemented

    used_by_delegates = []

    def validate_and_pre_save_impl(self, middleware, verrors, schema_name, attributes):
        pass

    async def validate_and_pre_save(self, middleware, verrors, schema_name, attributes):
        """If blocking I/O must be called in here, then put the logic in the *_impl method
        and call it using asyncio.to_thread"""
        pass


class KeychainCredentialUsedByDelegate:
    unbind_method = NotImplemented

    def __init__(self, middleware):
        self.middleware = middleware

    async def query(self, id_):
        raise NotImplementedError

    async def get_title(self, row):
        raise NotImplementedError

    async def unbind(self, row):
        raise NotImplementedError


class KeychainCredentialUsedByDelegateUnbindMethod(enum.Enum):
    DELETE = "delete"
    DISABLE = "disable"


class OtherKeychainCredentialKeychainCredentialUsedByDelegate(KeychainCredentialUsedByDelegate):
    unbind_method = KeychainCredentialUsedByDelegateUnbindMethod.DELETE

    type = NotImplemented

    async def query(self, id_):
        result = []
        for row in await self.middleware.call("keychaincredential.query", [["type", "=", self.type]]):
            if await self._is_related(row, id_):
                result.append(row)

        return result

    async def get_title(self, row):
        return f"{TYPES[self.type].title} {row['name']}"

    async def unbind(self, row):
        await self.middleware.call("keychaincredential.delete", row["id"], {"cascade": True})

    async def _is_related(self, row, id_):
        raise NotImplementedError


class SSHCredentialsSSHKeyPairUsedByDelegate(OtherKeychainCredentialKeychainCredentialUsedByDelegate):
    type = "SSH_CREDENTIALS"

    async def _is_related(self, row, id_):
        return row["attributes"]["private_key"] == id_


class SFTPCloudSyncCredentialsSSHKeyPairUsedByDelegate(KeychainCredentialUsedByDelegate):
    unbind_method = KeychainCredentialUsedByDelegateUnbindMethod.DISABLE

    async def query(self, id_):
        result = []
        for cloud_credentials in await self.middleware.call(
            "cloudsync.credentials.query", [["provider.type", "=", "SFTP"]]
        ):
            if cloud_credentials["provider"].get("private_key") == id_:
                result.append(cloud_credentials)

        return result

    async def get_title(self, row):
        return f"Cloud credentials {row['name']}"

    async def unbind(self, row):
        row["attributes"].pop("private_key")
        await self.middleware.call("datastore.update", "system.cloudcredentials", row["id"], {
            "attributes": row["attributes"]
        })


class SSHKeyPair(KeychainCredentialType):
    name = "SSH_KEY_PAIR"
    title = "SSH Key Pair"

    used_by_delegates = [
        SSHCredentialsSSHKeyPairUsedByDelegate,
        SFTPCloudSyncCredentialsSSHKeyPairUsedByDelegate,
    ]

    def validate_and_pre_save_impl(self, middleware, verrors, schema_name, attributes):
        opts = {"capture_output": True, "check": False, "encoding": "utf8"}
        if attributes["private_key"]:
            # TODO: It would be best if we use crypto plugin for this but as of right now we don't have support
            #  for openssh keys -
            #  https://stackoverflow.com/questions/59029092/how-to-load-openssh-private-key-using-cryptography-python-module
            #  so we keep on using ssh-keygen for now until that is properly supported in cryptography module.

            attributes["private_key"] = (attributes["private_key"].strip()) + "\n"
            with tempfile.NamedTemporaryFile("w+") as f:
                os.fchmod(f.file.fileno(), 0o600)

                f.write(attributes["private_key"])
                f.flush()

                proc = subprocess.run(["ssh-keygen", "-y", "-f", f.name], **opts)
                if proc.returncode == 0:
                    public_key = proc.stdout
                else:
                    if proc.stderr.startswith("Enter passphrase:"):
                        error = "Encrypted private keys are not allowed"
                    else:
                        error = proc.stderr

                    verrors.add(f"{schema_name}.private_key", error)
                    return

            if attributes["public_key"]:
                if self._normalize_public_key(attributes["public_key"]) != self._normalize_public_key(public_key):
                    verrors.add(f"{schema_name}.public_key", "Private key and public key do not match")
            else:
                attributes["public_key"] = public_key

        elif not attributes["public_key"]:
            verrors.add(f"{schema_name}.public_key", "You must specify a key")
            return

        with tempfile.NamedTemporaryFile("w+") as f:
            os.fchmod(f.file.fileno(), 0o600)

            f.write(attributes["public_key"])
            f.flush()

            proc = subprocess.run(["ssh-keygen", "-l", "-f", f.name], **opts)
            if proc.returncode != 0:
                verrors.add(f"{schema_name}.public_key", "Invalid public key")
                return

    async def validate_and_pre_save(self, middleware, verrors, schema_name, attributes):
        return await asyncio.to_thread(
            self.validate_and_pre_save_impl, middleware, verrors, schema_name, attributes
        )

    def _normalize_public_key(self, public_key):
        return " ".join(public_key.split()[:2]).strip()


class ReplicationTaskSSHCredentialsUsedByDelegate(KeychainCredentialUsedByDelegate):
    unbind_method = KeychainCredentialUsedByDelegateUnbindMethod.DISABLE

    async def query(self, id_):
        return await self.middleware.call("replication.query", [["ssh_credentials.id", "=", id_]])

    async def get_title(self, row):
        return f"Replication task {row['name']}"

    async def unbind(self, row):
        await self.middleware.call("datastore.update", "storage.replication", row["id"], {
            "repl_enabled": False,
            "repl_ssh_credentials": None,
        })
        await self.middleware.call("zettarepl.update_tasks")


class RsyncTaskSSHCredentialsUsedByDelegate(KeychainCredentialUsedByDelegate):
    unbind_method = KeychainCredentialUsedByDelegateUnbindMethod.DISABLE

    async def query(self, id_):
        return await self.middleware.call("rsynctask.query", [["ssh_credentials.id", "=", id_]])

    async def get_title(self, row):
        return f"Rsync task for {row['path']!r}"

    async def unbind(self, row):
        await self.middleware.call("rsynctask.update", row["id"], {"enabled": False})
        await self.middleware.call("datastore.update", "tasks.rsync", row["id"], {
            "rsync_ssh_credentials": None,
        })


class SSHCredentials(KeychainCredentialType):
    name = "SSH_CREDENTIALS"
    title = "SSH credentials"

    used_by_delegates = [
        ReplicationTaskSSHCredentialsUsedByDelegate,
        RsyncTaskSSHCredentialsUsedByDelegate,
    ]


TYPES = {
    type_.name: type_()
    for type_ in [SSHKeyPair, SSHCredentials]
}


def process_ssh_keyscan_output(output):
    return "\n".join([" ".join(line.split()[1:]) for line in output.split("\n") if line and not line.startswith("# ")])


class KeychainCredentialModel(sa.Model):
    __tablename__ = 'system_keychaincredential'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(255))
    type = sa.Column(sa.String(255))
    attributes = sa.Column(sa.JSON(encrypted=True))


class KeychainCredentialGetOfTypeArgs(BaseModel):
    id: int
    type: Literal["SSH_KEY_PAIR", "SSH_CREDENTIALS"]


class KeychainCredentialGetOfTypeResult(BaseModel):
    result: SSHKeyPairEntry | SSHCredentialsEntry


@single_argument_args("keychain_ssh_pair")
class KeychainCredentialSSHPairArgs(BaseModel):
    remote_hostname: NonEmptyString
    username: str = "root"
    public_key: NonEmptyString


@single_argument_result
class KeychainCredentialSSHPairResult(BaseModel):
    port: int
    host_key: LongString


class KeychainCredentialService(CRUDService):

    class Config:
        datastore = "system.keychaincredential"
        cli_namespace = "system.keychain_credential"
        role_prefix = "KEYCHAIN_CREDENTIAL"
        entry = KeychainCredentialEntry

    @api_method(
        KeychainCredentialCreateArgs,
        KeychainCredentialCreateResult,
        audit="Create Keychain Credential:",
        audit_extended=lambda data: data["name"]
    )
    async def do_create(self, data):
        """
        Create a Keychain Credential.

        The following `type`s are supported:
         * `SSH_KEY_PAIR`
         * `SSH_CREDENTIALS`

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "keychaincredential.create",
                "params": [{
                    "name": "Work SSH connection",
                    "type": "SSH_CREDENTIALS",
                    "attributes": {
                        "host": "work.freenas.org",
                        "private_key": 12,
                        "remote_host_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMn1VjdSMatGnxbOsrneKyai+dh6d4Hm"
                    }
                }]
            }
        """
        await self._validate("keychain_credential_create", data)

        data["id"] = await self.middleware.call(
            "datastore.insert",
            self._config.datastore,
            data,
        )
        return data

    @api_method(
        KeychainCredentialUpdateArgs,
        KeychainCredentialUpdateResult,
        audit="Update Keychain Credential:",
        audit_callback=True
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update a Keychain Credential with specific `id`.

        Please note that you can't change `type`. You must specify full `attributes` value.

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "keychaincredential.update",
                "params": [
                    13,
                    {
                        "name": "Work SSH connection",
                        "attributes": {
                            "host": "work.ixsystems.com",
                            "private_key": 12,
                            "remote_host_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMn1VjdSMatGnxbOsrneKyai+dh6d4Hm"
                        }
                    }
                ]
            }
        """
        old = await self.get_instance(id_)
        audit_callback(old["name"])

        new = old.copy()
        new.update(data)

        await self._validate("keychain_credentials_update", new, id_)

        await self.middleware.call(
            "datastore.update",
            self._config.datastore,
            id_,
            new,
        )

        await self.middleware.call("zettarepl.update_tasks")

        return new

    @api_method(
        KeychainCredentialDeleteArgs,
        KeychainCredentialDeleteResult,
        audit="Delete Keychain Credential:",
        audit_callback=True
    )
    async def do_delete(self, audit_callback, id_, options):
        """
        Delete Keychain Credential with specific `id`.

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "keychaincredential.delete",
                "params": [
                    13
                ]
            }
        """
        instance = await self.get_instance(id_)
        audit_callback(instance["name"])

        for delegate in TYPES[instance["type"]].used_by_delegates:
            delegate = delegate(self.middleware)
            for row in await delegate.query(instance["id"]):
                if not options["cascade"]:
                    raise ValidationError(
                        "options.cascade",
                        "This credential is used and no cascade option is specified"
                    )
                await delegate.unbind(row)

        await self.middleware.call(
            "datastore.delete",
            self._config.datastore,
            id_,
        )

    @api_method(KeychainCredentialUsedByArgs, KeychainCredentialUsedByResult, roles=['KEYCHAIN_CREDENTIAL_READ'])
    async def used_by(self, id_):
        """
        Returns list of objects that use this credential.
        """
        instance = await self.get_instance(id_)

        result = []
        for delegate in TYPES[instance["type"]].used_by_delegates:
            delegate = delegate(self.middleware)
            for row in await delegate.query(instance["id"]):
                result.append({
                    "title": await delegate.get_title(row),
                    "unbind_method": delegate.unbind_method.value,
                })
                if isinstance(delegate, OtherKeychainCredentialKeychainCredentialUsedByDelegate):
                    result.extend(await self.middleware.call("keychaincredential.used_by", row["id"]))
        return result

    async def _validate(self, schema_name, data, id_=None):
        verrors = ValidationErrors()

        await self._ensure_unique(verrors, schema_name, "name", data["name"], id_)
        verrors.check()

        type_ = TYPES[data["type"]]
        await type_.validate_and_pre_save(self.middleware, verrors, f"{schema_name}.attributes", data["attributes"])
        verrors.check()

    @api_method(KeychainCredentialGetOfTypeArgs, KeychainCredentialGetOfTypeResult, private=True)
    async def get_of_type(self, id_, type_):
        try:
            credential = await self.middleware.call("keychaincredential.query", [["id", "=", id_]], {"get": True})
        except MatchNotFound:
            raise CallError("Credential does not exist", errno.ENOENT)
        else:
            if credential["type"] != type_:
                raise CallError(f"Credential is not of type {type_}", errno.EINVAL)

            if not credential["attributes"]:
                raise CallError(f"Decrypting credential {credential['name']} failed", errno.EFAULT)

            return credential

    @api_method(
        KeychainCredentialGenerateSshKeyPairArgs,
        KeychainCredentialGenerateSshKeyPairResult,
        roles=["KEYCHAIN_CREDENTIAL_WRITE"]
    )
    def generate_ssh_key_pair(self):
        """
        Generate a public/private key pair (useful for `SSH_KEY_PAIR` type)

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "keychaincredential.generate_ssh_key_pair",
                "params": []
            }
        """
        with tempfile.TemporaryDirectory() as tmpdirname:
            key = os.path.join(tmpdirname, "key")
            subprocess.check_call(["ssh-keygen", "-t", "rsa", "-f", key, "-N", "", "-q"])
            with open(key) as f:
                private_key = f.read()
            with open(f"{key}.pub") as f:
                public_key = f.read()

        return {
            "private_key": private_key,
            "public_key": public_key,
        }

    @api_method(
        KeychainCredentialRemoteSshHostKeyScanArgs,
        KeychainCredentialRemoteSshHostKeyScanResult,
        roles=["KEYCHAIN_CREDENTIAL_WRITE"]
    )
    async def remote_ssh_host_key_scan(self, data):
        """
        Discover a remote host key (useful for `SSH_CREDENTIALS`)

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "keychaincredential.delete",
                "params": [{
                    "host": "work.freenas.org"
                }]
            }
        """

        proc = await run(["ssh-keyscan", "-p", str(data["port"]), "-T", str(data["connect_timeout"]), data["host"]],
                         check=False, encoding="utf8")
        if proc.returncode == 0:
            if proc.stdout:
                try:
                    return process_ssh_keyscan_output(proc.stdout)
                except Exception:
                    raise CallError(f"ssh-keyscan failed: {proc.stdout + proc.stderr}") from None
            elif proc.stderr:
                raise CallError(f"ssh-keyscan failed: {proc.stderr}")
            else:
                raise CallError("SSH timeout")
        else:
            raise CallError(f"ssh-keyscan failed: {proc.stdout + proc.stderr}")

    @api_method(
        KeychainCredentialRemoteSshSemiautomaticSetupArgs,
        KeychainCredentialRemoteSshSemiautomaticSetupResult,
        roles=["KEYCHAIN_CREDENTIAL_WRITE"],
        audit="SSH Semi-automatic Setup:",
        audit_extended=lambda data: data["name"]
    )
    def remote_ssh_semiautomatic_setup(self, data):
        """
        Perform semi-automatic SSH connection setup with other TrueNAS machine.

        It creates an `SSH_CREDENTIALS` credential with specified `name` that can be used to connect to TrueNAS machine
        with specified `url` and temporary auth `token`. Other TrueNAS machine adds `private_key` to allowed
        `username`'s private keys. Other `SSH_CREDENTIALS` attributes such as `connect_timeout` can be specified as
        well.

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "keychaincredential.remote_ssh_semiautomatic_setup",
                "params": [{
                    "name": "Work SSH connection",
                    "url": "https://work.freenas.org",
                    "token": "8c8d5fd1-f749-4429-b379-9c186db4f834",
                    "private_key": 12
                }]
            }
        """
        replication_key = self.middleware.call_sync("keychaincredential.get_ssh_key_pair_with_private_key",
                                                    data["private_key"])

        try:
            client = Client(os.path.join(re.sub("^http", "ws", data["url"]), "websocket"),
                            verify_ssl=data["verify_ssl"])
        except ssl.SSLCertVerificationError as e:
            raise CallError(str(e), CallError.ESSLCERTVERIFICATIONERROR)
        except Exception as e:
            raise CallError(f"Unable to connect to remote system: {e}")

        with client as c:
            if data["token"]:
                if not c.call("auth.login_with_token", data["token"]):
                    raise CallError("Invalid token")
            elif data["password"]:
                args = [data["admin_username"], data["password"]]
                if data["otp_token"]:
                    args.append(data["otp_token"])
                if not c.call("auth.login", *args):
                    raise CallError("Invalid username or password")
            else:
                raise CallError("You should specify either remote system password or temporary authentication token")

            try:
                response = c.call("keychaincredential.ssh_pair", {
                    "remote_hostname": "any-host",
                    "username": data["username"],
                    "public_key": replication_key["attributes"]["public_key"],
                })
            except ClientException as e:
                raise CallError(
                    f"Semi-automatic SSH connection setup failed: {e}\n\n"
                    f"Please make sure that home directory for {data['username']} user on the remote system exists and "
                    "is writeable."
                )
            except Exception as e:
                raise CallError(f"Semi-automatic SSH connection setup failed: {e!r}")

            user = c.call("user.query", [["username", "=", data["username"]], ['local', '=', True]], {"get": True})
            user_update = {}
            if user["shell"] == NO_LOGIN_SHELL:
                user_update["shell"] = "/usr/bin/bash"
            if data["sudo"]:
                if "ALL" not in user["sudo_commands_nopasswd"]:
                    zfs_binary = "/usr/sbin/zfs"
                    if zfs_binary not in user["sudo_commands_nopasswd"]:
                        user_update["sudo_commands_nopasswd"] = user["sudo_commands_nopasswd"] + [zfs_binary]
            try:
                c.call("user.update", user["id"], user_update)
            except Exception as e:
                raise CallError(f"Error updating remote user attributes: {e}")

        return self.middleware.call_sync("keychaincredential.create", {
            "name": data["name"],
            "type": "SSH_CREDENTIALS",
            "attributes": {
                "host": urllib.parse.urlparse(data["url"]).hostname,
                "port": response["port"],
                "username": data["username"],
                "private_key": replication_key["id"],
                "remote_host_key": process_ssh_keyscan_output(response["host_key"]),
                "connect_timeout": data["connect_timeout"],
            }
        })

    @api_method(KeychainCredentialSSHPairArgs, KeychainCredentialSSHPairResult, private=True)
    def ssh_pair(self, data):
        """
        Receives public key, storing it to accept SSH connection and return
        pertinent SSH data of this machine.
        """
        service = self.middleware.call_sync("service.query", [("service", "=", "ssh")], {"get": True})
        ssh = self.middleware.call_sync("ssh.config")
        try:
            user = self.middleware.call_sync(
                "user.query",
                [("username", "=", data["username"]), ("local", "=", True)],
                {"get": True}
            )
        except MatchNotFound:
            raise CallError(f"User {data['username']} does not exist")

        if user["home"].startswith("/var/empty") or not os.path.exists(user["home"]):
            raise CallError(f"Home directory {user['home']} does not exist", errno.ENOENT)

        # Make sure SSH is enabled
        if not service["enable"]:
            self.middleware.call_sync("service.update", "ssh", {"enable": True})

        if service["state"] != "RUNNING":
            self.middleware.call_sync("service.control", "START", "ssh").wait_sync(raise_error=True)

            # This might be the first time of the service being enabled
            # which will then result in new host keys we need to grab
            ssh = self.middleware.call_sync("ssh.config")

        # Write public key in user authorized_keys for SSH
        pubkey = (user["sshpubkey"] or "").strip()
        if data["public_key"] not in pubkey:
            pubkey += "\n" + data["public_key"] + "\n"
            self.middleware.call_sync("user.update", user["id"], {"sshpubkey": pubkey})

        ssh_hostkey = "{0} {1}\n{0} {2}\n{0} {3}\n".format(
            data["remote_hostname"],
            base64.b64decode(ssh["host_rsa_key_pub"].encode()).decode(),
            base64.b64decode(ssh["host_ecdsa_key_pub"].encode()).decode(),
            base64.b64decode(ssh["host_ed25519_key_pub"].encode()).decode(),
        )

        return {
            "port": ssh["tcpport"],
            "host_key": ssh_hostkey,
        }

    @private
    async def get_ssh_key_pair_with_private_key(self, id_):
        try:
            credential = await self.middleware.call("keychaincredential.query", [["id", "=", id_]], {"get": True})
        except MatchNotFound:
            return None

        if credential["type"] != "SSH_KEY_PAIR":
            return None

        if not credential["attributes"]["private_key"]:
            return None

        return credential
