import base64
import os
import subprocess

import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import (
    SSHEntry, SSHBindifaceChoicesArgs, SSHBindifaceChoicesResult, SSHUpdateArgs, SSHUpdateResult
)
from middlewared.async_validators import validate_port
from middlewared.common.ports import ServicePortDelegate
from middlewared.schema import ValidationErrors
from middlewared.service import private, SystemServiceService


class SSHModel(sa.Model):
    __tablename__ = 'services_ssh'

    id = sa.Column(sa.Integer(), primary_key=True)
    ssh_bindiface = sa.Column(sa.MultiSelectField(), default=[])
    ssh_tcpport = sa.Column(sa.Integer(), default=22)
    ssh_password_login_groups = sa.Column(sa.JSON(list))
    ssh_passwordauth = sa.Column(sa.Boolean(), default=False)
    ssh_kerberosauth = sa.Column(sa.Boolean(), default=False)
    ssh_tcpfwd = sa.Column(sa.Boolean(), default=False)
    ssh_compression = sa.Column(sa.Boolean(), default=False)
    ssh_privatekey = sa.Column(sa.EncryptedText())
    ssh_sftp_log_level = sa.Column(sa.String(20))
    ssh_sftp_log_facility = sa.Column(sa.String(20))
    ssh_host_dsa_key = sa.Column(sa.EncryptedText(), nullable=True)
    ssh_host_dsa_key_pub = sa.Column(sa.Text(), nullable=True)
    ssh_host_dsa_key_cert_pub = sa.Column(sa.Text(), nullable=True)
    ssh_host_ecdsa_key = sa.Column(sa.EncryptedText(), nullable=True)
    ssh_host_ecdsa_key_pub = sa.Column(sa.Text(), nullable=True)
    ssh_host_ecdsa_key_cert_pub = sa.Column(sa.Text(), nullable=True)
    ssh_host_ed25519_key = sa.Column(sa.EncryptedText(), nullable=True)
    ssh_host_ed25519_key_pub = sa.Column(sa.Text(), nullable=True)
    ssh_host_ed25519_key_cert_pub = sa.Column(sa.Text(), nullable=True)
    ssh_host_key = sa.Column(sa.EncryptedText(), nullable=True)
    ssh_host_key_pub = sa.Column(sa.Text(), nullable=True)
    ssh_host_rsa_key = sa.Column(sa.EncryptedText(), nullable=True)
    ssh_host_rsa_key_pub = sa.Column(sa.Text(), nullable=True)
    ssh_host_rsa_key_cert_pub = sa.Column(sa.Text(), nullable=True)
    ssh_weak_ciphers = sa.Column(sa.JSON(list))
    ssh_options = sa.Column(sa.Text())


class SSHService(SystemServiceService):

    class Config:
        datastore = "services.ssh"
        service = "ssh"
        datastore_prefix = "ssh_"
        cli_namespace = 'service.ssh'
        role_prefix = 'SSH'
        entry = SSHEntry

    @api_method(SSHBindifaceChoicesArgs, SSHBindifaceChoicesResult, roles=['NETWORK_INTERFACE_READ'])
    def bindiface_choices(self):
        """
        Available choices for the bindiface attribute of SSH service.
        """
        return self.middleware.call_sync('interface.choices')

    @api_method(SSHUpdateArgs, SSHUpdateResult, audit='Update SSH configuration')
    async def do_update(self, data):
        """
        Update settings of SSH daemon service.

        If `bindiface` is empty it will listen for all available addresses.

        .. examples(websocket)::

          Make sshd listen only to igb0 interface.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "ssh.update",
                "params": [{
                    "bindiface": ["igb0"]
                }]
            }

        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        if new['bindiface']:
            iface_choices = await self.middleware.call('ssh.bindiface_choices')
            invalid_ifaces = list(filter(lambda x: x not in iface_choices, new['bindiface']))
            if invalid_ifaces:
                verrors.add(
                    'ssh_update.bindiface',
                    f'The following interfaces are not valid: {", ".join(invalid_ifaces)}',
                )

        verrors.extend(await validate_port(self.middleware, 'ssh_update.tcpport', new['tcpport'], 'ssh'))
        verrors.check()

        await self._update_service(old, new)

        return await self.config()

    keys = [
        (
            os.path.join("/etc/ssh", i),
            i.replace(".", "_",).replace("-", "_")
        )
        for i in [
            "ssh_host_key",
            "ssh_host_key.pub",
            "ssh_host_dsa_key",
            "ssh_host_dsa_key.pub",
            "ssh_host_dsa_key-cert.pub",
            "ssh_host_ecdsa_key",
            "ssh_host_ecdsa_key.pub",
            "ssh_host_ecdsa_key-cert.pub",
            "ssh_host_rsa_key",
            "ssh_host_rsa_key.pub",
            "ssh_host_rsa_key-cert.pub",
            "ssh_host_ed25519_key",
            "ssh_host_ed25519_key.pub",
            "ssh_host_ed25519_key-cert.pub",
        ]
    ]

    @private
    def cleanup_keys(self):
        config = self.middleware.call_sync("datastore.config", "services.ssh")
        for path, column in self.keys:
            if not config[column] and os.path.exists(path):
                self.middleware.logger.warning("Removing irrelevant SSH host key %r", path)
                os.unlink(path)

    @private
    def generate_keys(self):
        self.middleware.logger.debug("Generating SSH host keys")
        p = subprocess.run(
            # For each of the key types (rsa, dsa, ecdsa and ed25519) for which host keys do not exist,
            # generate the host keys with the default key file path, an empty passphrase, default bits
            # for the key type, and default comment.
            ["ssh-keygen", "-A"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="ignore"
        )
        if p.returncode != 0:
            self.middleware.logger.error("Error generating SSH host keys: %s", p.stdout)

    @private
    def save_keys(self):
        update = {}
        old = self.middleware.call_sync('datastore.query', 'services_ssh', [], {'get': True})
        for path, column in self.keys:
            if os.path.exists(path):
                with open(path, "rb") as f:
                    data = base64.b64encode(f.read()).decode("ascii")
                    if data != old[column]:
                        update[column] = data

        if update:
            self.middleware.call_sync('datastore.update', 'services.ssh', old['id'], update, {'ha_sync': False})


class SSHServicePortDelegate(ServicePortDelegate):

    name = 'ssh'
    namespace = 'ssh'
    port_fields = ['tcpport']
    title = 'SSH Service'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', SSHServicePortDelegate(middleware))
    if await middleware.call('core.is_starting_during_boot'):
        await middleware.call('ssh.cleanup_keys')
        await middleware.call('ssh.generate_keys')
