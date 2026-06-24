from middlewared.api.current import SSHEntry, SSHUpdate
from middlewared.async_validators import validate_port
from middlewared.service import SystemServicePart, ValidationErrors
import middlewared.sqlalchemy as sa


class SSHModel(sa.Model):
    __tablename__ = "services_ssh"

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


class SSHServicePart(SystemServicePart[SSHEntry]):
    _datastore = "services.ssh"
    _datastore_prefix = "ssh_"
    _entry = SSHEntry
    _service = "ssh"

    async def do_update(self, data: SSHUpdate) -> SSHEntry:
        old = await self.config()
        new = old.updated(data)

        verrors = ValidationErrors()
        if new.bindiface:
            iface_choices = await self.call2(self.s.ssh.bindiface_choices)
            invalid_ifaces = [iface for iface in new.bindiface if iface not in iface_choices]
            if invalid_ifaces:
                verrors.add(
                    "ssh_update.bindiface",
                    f"The following interfaces are not valid: {', '.join(invalid_ifaces)}",
                )

        verrors.extend(await validate_port(self.middleware, "ssh_update.tcpport", new.tcpport, "ssh"))
        verrors.check()

        update = new.model_dump()
        update.pop("id", None)
        await self._update_service(old.id, update)

        return await self.config()
