import base64
import enum
import errno
import os
import random
import re
import string
import subprocess
import tempfile
import urllib.parse

from middlewared.client import Client
from middlewared.service_exception import CallError
from middlewared.schema import accepts, Bool, Dict, Int, List, Patch, Ref, returns, Str, ValidationErrors
from middlewared.service import CRUDService, private
import middlewared.sqlalchemy as sa
from middlewared.utils import run
from middlewared.validators import validate_attributes, URL


class KeychainCredentialType:
    name = NotImplemented
    title = NotImplemented

    credentials_schema = NotImplemented

    used_by_delegates = []

    async def validate_and_pre_save(self, middleware, verrors, schema_name, attributes):
        pass


class KeychainCredentialUsedByDelegate:
    unbind_method = NotImplemented

    def __init__(self, middleware):
        self.middleware = middleware

    async def query(self, id):
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

    async def query(self, id):
        result = []
        for row in await self.middleware.call("keychaincredential.query", [["type", "=", self.type]]):
            if await self._is_related(row, id):
                result.append(row)

        return result

    async def get_title(self, row):
        return f"{TYPES[self.type].title} {row['name']}"

    async def unbind(self, row):
        await self.middleware.call("keychaincredential.delete", row["id"], {"cascade": True})

    async def _is_related(self, row, id):
        raise NotImplementedError


class SSHCredentialsSSHKeyPairUsedByDelegate(OtherKeychainCredentialKeychainCredentialUsedByDelegate):
    type = "SSH_CREDENTIALS"

    async def _is_related(self, row, id):
        return row["attributes"]["private_key"] == id


class SFTPCloudSyncCredentialsSSHKeyPairUsedByDelegate(KeychainCredentialUsedByDelegate):
    unbind_method = KeychainCredentialUsedByDelegateUnbindMethod.DISABLE

    async def query(self, id):
        result = []
        for cloud_credentials in await self.middleware.call("cloudsync.credentials.query", [["provider", "=", "SFTP"]]):
            if cloud_credentials["attributes"].get("private_key") == id:
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

    credentials_schema = [
        Str("private_key", null=True, default=None, max_length=None),
        Str("public_key", null=True, default=None, max_length=None),
    ]

    used_by_delegates = [
        SSHCredentialsSSHKeyPairUsedByDelegate,
        SFTPCloudSyncCredentialsSSHKeyPairUsedByDelegate,
    ]

    async def validate_and_pre_save(self, middleware, verrors, schema_name, attributes):
        if attributes["private_key"]:
            # TODO: It would be best if we use crypto plugin for this but as of right now we don't have support
            #  for openssh keys -
            #  https://stackoverflow.com/questions/59029092/how-to-load-openssh-private-key-using-cryptography-python-module
            #  so we keep on using ssh-keygen for now until that is properly supported in cryptography module.

            attributes["private_key"] = (attributes["private_key"].strip()) + "\n"
            with tempfile.NamedTemporaryFile("w+") as f:
                os.chmod(f.name, 0o600)

                f.write(attributes["private_key"])
                f.flush()

                proc = await run(["ssh-keygen", "-y", "-f", f.name], check=False, encoding="utf8")
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

        if not attributes["public_key"]:
            verrors.add(f"{schema_name}.public_key", "You must specify at least public key")
            return

        with tempfile.NamedTemporaryFile("w+") as f:
            os.chmod(f.name, 0o600)

            f.write(attributes["public_key"])
            f.flush()

            proc = await run(["ssh-keygen", "-l", "-f", f.name], check=False, encoding="utf8")
            if proc.returncode != 0:
                verrors.add(f"{schema_name}.public_key", "Invalid public key")
                return

    def _normalize_public_key(self, public_key):
        return " ".join(public_key.split()[:2]).strip()


class ReplicationTaskSSHCredentialsUsedByDelegate(KeychainCredentialUsedByDelegate):
    unbind_method = KeychainCredentialUsedByDelegateUnbindMethod.DISABLE

    async def query(self, id):
        return await self.middleware.call("replication.query", [["ssh_credentials.id", "=", id]])

    async def get_title(self, row):
        return f"Replication task {row['name']}"

    async def unbind(self, row):
        await self.middleware.call("replication.update", row["id"], {"enabled": False})
        await self.middleware.call("datastore.update", "storage.replication", row["id"], {
            "repl_ssh_credentials": None,
        })


class SSHCredentials(KeychainCredentialType):
    name = "SSH_CREDENTIALS"
    title = "SSH credentials"

    credentials_schema = [
        Str("host", required=True),
        Int("port", default=22),
        Str("username", default="root"),
        Int("private_key", required=True),
        Str("remote_host_key", required=True),
        Str("cipher", enum=["STANDARD", "FAST", "DISABLED"], default="STANDARD"),
        Int("connect_timeout", default=10),
    ]

    used_by_delegates = [
        ReplicationTaskSSHCredentialsUsedByDelegate,
    ]


TYPES = {
    type.name: type()
    for type in [SSHKeyPair, SSHCredentials]
}


async def get_ssh_key_pair_with_private_key(middleware, id):
    try:
        credential = await middleware.call("keychaincredential.query", [["id", "=", id]], {"get": True})
    except IndexError:
        return None

    if credential["type"] != "SSH_KEY_PAIR":
        return None

    if not credential["attributes"]["private_key"]:
        return None

    return credential


def process_ssh_keyscan_output(output):
    return "\n".join([" ".join(line.split()[1:]) for line in output.split("\n") if line and not line.startswith("# ")])


class KeychainCredentialModel(sa.Model):
    __tablename__ = 'system_keychaincredential'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(255))
    type = sa.Column(sa.String(255))
    attributes = sa.Column(sa.JSON(encrypted=True))


class KeychainCredentialService(CRUDService):

    class Config:
        datastore = "system.keychaincredential"
        cli_namespace = "system.keychain_credential"

    ENTRY = Patch(
        "keychain_credential_create", "keychain_credential_entry",
        ("add", Int("id")),
    )

    @accepts(Dict(
        "keychain_credential_create",
        Str("name", required=True),
        Str("type", required=True),
        Dict("attributes", additional_attrs=True, required=True, private=True),
        register=True,
    ))
    async def do_create(self, data):
        """
        Create a Keychain Credential

        Create a Keychain Credential of any type.
        Every Keychain Credential has a `name` which is used to distinguish it from others.
        The following `type`s are supported:
         * `SSH_KEY_PAIR`
           Which `attributes` are:
           * `private_key`
           * `public_key` (which can be omitted and thus automatically derived from private key)
           At least one attribute is required.

         * `SSH_CREDENTIALS`
           Which `attributes` are:
           * `host`
           * `port` (default 22)
           * `username` (default root)
           * `private_key` (Keychain Credential ID)
           * `remote_host_key` (you can use `keychaincredential.remote_ssh_host_key_scan` do discover it)
           * `cipher`: one of `STANDARD`, `FAST`, or `DISABLED` (last requires special support from both SSH server and
             client)
           * `connect_timeout` (default 10)

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

    @accepts(
        Int("id"),
        Patch(
            "keychain_credential_create",
            "keychain_credential_update",
            ("attr", {"update": True}),
            ("rm", {"name": "type"}),
        )
    )
    async def do_update(self, id, data):
        """
        Update a Keychain Credential with specific `id`

        Please note that you can't change `type`

        Also you must specify full `attributes` value

        See the documentation for `create` method for information on payload contents

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

        old = await self._get_instance(id)

        new = old.copy()
        new.update(data)

        await self._validate("keychain_credentials_update", new, id)

        await self.middleware.call(
            "datastore.update",
            self._config.datastore,
            id,
            new,
        )

        if new["type"] in ["SSH_KEY_PAIR", "SSH_CREDENTIALS"]:
            await self.middleware.call("zettarepl.update_tasks")

        return new

    @accepts(Int("id"), Dict("options", Bool("cascade", default=False)))
    @returns()
    async def do_delete(self, id, options):
        """
        Delete Keychain Credential with specific `id`

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

        instance = await self._get_instance(id)

        for delegate in TYPES[instance["type"]].used_by_delegates:
            delegate = delegate(self.middleware)
            for row in await delegate.query(instance["id"]):
                if not options["cascade"]:
                    raise CallError("This credential is used and no cascade option is specified")

                await delegate.unbind(row)

        await self.middleware.call(
            "datastore.delete",
            self._config.datastore,
            id,
        )

    @accepts(Int("id"))
    @returns(List("credential_results", items=[Dict(
        "credential_result",
        Str("title"),
        Str("unbind_method"),
    )]))
    async def used_by(self, id):
        """
        Returns list of objects that use this credential.
        """
        instance = await self._get_instance(id)

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

    async def _validate(self, schema_name, data, id=None):
        verrors = ValidationErrors()

        await self._ensure_unique(verrors, schema_name, "name", data["name"], id)

        if data["type"] not in TYPES:
            verrors.add(f"{schema_name}.type", "Invalid type")
            raise verrors
        else:
            type = TYPES[data["type"]]

            attributes_verrors = validate_attributes(type.credentials_schema, data)
            verrors.add_child(f"{schema_name}.attributes", attributes_verrors)

        if verrors:
            raise verrors

        await type.validate_and_pre_save(self.middleware, verrors, f"{schema_name}.attributes", data["attributes"])

        if verrors:
            raise verrors

    @private
    @accepts(Int("id"), Str("type"))
    @returns(Ref("keychain_credential_entry"))
    async def get_of_type(self, id, type):
        try:
            credential = await self.middleware.call("keychaincredential.query", [["id", "=", id]], {"get": True})
        except IndexError:
            raise CallError("Credential does not exist", errno.ENOENT)
        else:
            if credential["type"] != type:
                raise CallError(f"Credential is not of type {type}", errno.EINVAL)

            if not credential["attributes"]:
                raise CallError(f"Decrypting credential {credential['name']} failed", errno.EFAULT)

            return credential

    @accepts()
    @returns(Dict(
        "ssh_key_pair",
        Str("private_key", max_length=None, required=True),
        Str("public_key", max_length=None, required=True),
    ))
    def generate_ssh_key_pair(self):
        """
        Generate a public/private key pair

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

        key = os.path.join("/tmp", "".join(random.choice(string.ascii_letters) for _ in range(32)))
        if os.path.exists(key):
            os.unlink(key)
        if os.path.exists(f"{key}.pub"):
            os.unlink(f"{key}.pub")
        try:
            subprocess.check_call(["ssh-keygen", "-t", "rsa", "-f", key, "-N", "", "-q"])
            with open(key) as f:
                private_key = f.read()
            with open(f"{key}.pub") as f:
                public_key = f.read()
        finally:
            if os.path.exists(key):
                os.unlink(key)
            if os.path.exists(f"{key}.pub"):
                os.unlink(f"{key}.pub")

        return {
            "private_key": private_key,
            "public_key": public_key,
        }

    @accepts(Dict(
        "keychain_remote_ssh_host_key_scan",
        Str("host", required=True, empty=False),
        Str("port", default=22),
        Int("connect_timeout", default=10),
    ))
    @returns(Str("remove_ssh_host_key", max_length=None))
    async def remote_ssh_host_key_scan(self, data):
        """
        Discover a remote host key

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

    @accepts(Dict(
        "keychain_remote_ssh_semiautomatic_setup",
        Str("name", required=True),
        Str("url", required=True, validators=[URL()]),
        Str("token", private=True),
        Str("password", private=True),
        Str("username", default="root"),
        Int("private_key", required=True),
        Str("cipher", enum=["STANDARD", "FAST", "DISABLED"], default="STANDARD"),
        Int("connect_timeout", default=10),
    ))
    @returns(Ref("keychain_credential_entry"))
    def remote_ssh_semiautomatic_setup(self, data):
        """
        Perform semi-automatic SSH connection setup with other FreeNAS machine

        Perform semi-automatic SSH connection setup with other FreeNAS machine. It creates a `SSH_CREDENTIALS`
        credential with specified `name` that can be used to connect to FreeNAS machine with specified `url` and
        temporary auth `token`. Other FreeNAS machine adds `private_key` to allowed `username`'s private keys. Other
        `SSH_CREDENTIALS` attributes such as `cipher` and `connect_timeout` can be specified as well.

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "keychaincredential.keychain_remote_ssh_semiautomatic_setup",
                "params": [{
                    "name": "Work SSH connection",
                    "url": "https://work.freenas.org",
                    "token": "8c8d5fd1-f749-4429-b379-9c186db4f834",
                    "private_key": 12
                }]
            }
        """

        replication_key = self.middleware.run_coroutine(
            get_ssh_key_pair_with_private_key(self.middleware, data["private_key"]))

        try:
            client = Client(os.path.join(re.sub("^http", "ws", data["url"]), "websocket"))
        except Exception as e:
            raise CallError(f"Unable to connect to remote system: {e}")

        with client as c:
            if data.get("token"):
                if not c.call("auth.token", data["token"]):
                    raise CallError("Invalid token")
            elif data.get("password"):
                if not c.call("auth.login", "root", data["password"]):
                    raise CallError("Invalid password")
            else:
                raise CallError("You should specify either remote system password or temporary authentication token")

            try:
                response = c.call("replication.pair", {
                    "hostname": "any-host",
                    "public-key": replication_key["attributes"]["public_key"],
                    "user": data["username"],
                })
            except Exception as e:
                raise CallError(f"Semi-automatic SSH connection setup failed: {e!r}")

        return self.middleware.call_sync("keychaincredential.create", {
            "name": data["name"],
            "type": "SSH_CREDENTIALS",
            "attributes": {
                "host": urllib.parse.urlparse(data["url"]).hostname,
                "port": response["ssh_port"],
                "username": data["username"],
                "private_key": replication_key["id"],
                "remote_host_key": process_ssh_keyscan_output(response["ssh_hostkey"]),
                "cipher": data["cipher"],
                "connect_timeout": data["connect_timeout"],
            }
        })

    @private
    @accepts(Dict(
        "keychain_ssh_pair",
        Str("remote_hostname", required=True),
        Str("username", default="root"),
        Str("public_key", required=True),
    ))
    async def ssh_pair(self, data):
        """
        Receives public key, storing it to accept SSH connection and return
        pertinent SSH data of this machine.
        """
        service = await self.middleware.call("service.query", [("service", "=", "ssh")], {"get": True})
        ssh = await self.middleware.call("ssh.config")
        try:
            user = await self.middleware.call("user.query", [("username", "=", data["username"])], {"get": True})
        except IndexError:
            raise CallError(f"User {data['username']} does not exist")

        if user["home"].startswith("/nonexistent") or not os.path.exists(user["home"]):
            raise CallError(f"Home directory {user['home']} does not exist", errno.ENOENT)

        # Make sure SSH is enabled
        if not service["enable"]:
            await self.middleware.call("service.update", "ssh", {"enable": True})

        if service["state"] != "RUNNING":
            await self.middleware.call("service.start", "ssh")

            # This might be the first time of the service being enabled
            # which will then result in new host keys we need to grab
            ssh = await self.middleware.call("ssh.config")

        # If .ssh dir does not exist, create it
        dotsshdir = os.path.join(user["home"], ".ssh")
        if not os.path.exists(dotsshdir):
            os.mkdir(dotsshdir)
            os.chown(dotsshdir, user["uid"], user["group"]["bsdgrp_gid"])

        # Write public key in user authorized_keys for SSH
        authorized_keys_file = f"{dotsshdir}/authorized_keys"
        with open(authorized_keys_file, "a+") as f:
            f.seek(0)
            if data["public_key"] not in f.read():
                f.write("\n" + data["public_key"] + "\n")

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
