from __future__ import annotations

import asyncio
import re
import tempfile
import textwrap
from typing import Any
import warnings

from middlewared.api.current import SystemAdvancedEntry, SystemAdvancedUpdate
from middlewared.plugins.initramfs import write_initramfs_flags
from middlewared.service import ConfigServicePart, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import run
from middlewared.utils.boot.models import BootUpdateInitramfsOptions
from middlewared.utils.service.settings import SettingsHelper

from .nvidia import handle_nvidia_toggle
from .serial import configure_tty, serial_port_choices

settings = SettingsHelper()


class SystemAdvancedModel(sa.Model):
    __tablename__ = 'system_advanced'

    id = sa.Column(sa.Integer(), primary_key=True)
    adv_consolemenu = sa.Column(sa.Boolean(), default=False)
    adv_serialconsole = sa.Column(sa.Boolean(), default=False)
    adv_serialport = sa.Column(sa.String(120), default='ttyS0')
    adv_serialspeed = sa.Column(sa.String(120), default='9600')
    adv_powerdaemon = sa.Column(sa.Boolean(), default=False)
    adv_overprovision = sa.Column(sa.Integer(), nullable=True, default=None)
    adv_traceback = sa.Column(sa.Boolean(), default=True)
    adv_advancedmode = sa.Column(sa.Boolean(), default=False)
    adv_autotune = sa.Column(sa.Boolean(), default=False)
    adv_debugkernel = sa.Column(sa.Boolean(), default=False)
    adv_uploadcrash = sa.Column(sa.Boolean(), default=True)
    adv_anonstats = sa.Column(sa.Boolean(), default=True)
    adv_anonstats_token = sa.Column(sa.Text())
    adv_motd = sa.Column(sa.Text(), default='Welcome')
    adv_login_banner = sa.Column(sa.Text(), default='')
    adv_boot_scrub = sa.Column(sa.Integer(), default=7)
    adv_fqdn_syslog = sa.Column(sa.Boolean(), default=False)
    adv_sed_user = sa.Column(sa.String(120), default='user')
    adv_sed_passwd = sa.Column(sa.EncryptedText(), default='')
    adv_sysloglevel = sa.Column(sa.String(120), default='f_info')
    adv_syslogservers = sa.Column(sa.JSON(list), default=[])
    adv_syslog_audit = sa.Column(sa.Boolean(), default=False)
    adv_kmip_uid = sa.Column(sa.String(255), nullable=True, default=None)
    adv_kdump_enabled = sa.Column(sa.Boolean(), default=False)
    adv_isolated_gpu_pci_ids = sa.Column(sa.JSON(list), default=[])
    adv_kernel_extra_options = sa.Column(sa.Text(), default='', nullable=False)
    adv_nvidia = sa.Column(sa.Boolean(), default=False)


def syslogd_changes(orig_config: dict[str, Any], new_config: dict[str, Any]) -> bool:
    """Return `True` if syslogd should be restarted to apply the new configuration."""
    if (
        orig_config['fqdn_syslog'] != new_config['fqdn_syslog']
        or orig_config['sysloglevel'].lower() != new_config['sysloglevel'].lower()
        or orig_config['syslog_audit'] != new_config['syslog_audit']
    ):
        return True
    # Convert syslogservers to sets to disregard ordering for the comparison
    orig_items_set = {frozenset(d.items()) for d in orig_config['syslogservers']}
    new_items_set = {frozenset(d.items()) for d in new_config['syslogservers']}
    return orig_items_set != new_items_set


class SystemAdvancedConfigServicePart(ConfigServicePart[SystemAdvancedEntry]):
    _datastore = 'system.advanced'
    _datastore_prefix = 'adv_'
    _entry = SystemAdvancedEntry

    async def extend(self, data: dict[str, Any]) -> dict[str, Any]:
        data['consolemsg'] = (await self.middleware.call('system.general.config'))['ui_consolemsg']

        if data.get('sed_user'):
            data['sed_user'] = data['sed_user'].upper()

        data.pop('sed_passwd')
        data.pop('kmip_uid')

        return data

    async def sed_global_password(self) -> str:
        """Returns the configured global SED password in clear-text if one is set, otherwise an empty string."""
        passwd = (await self.middleware.call(
            'datastore.config', self._datastore, {'prefix': self._datastore_prefix}
        ))['sed_passwd']
        if passwd:
            return str(passwd)
        return str(await self.middleware.call('kmip.sed_global_password'))

    def login_banner(self) -> str:
        return str(self.middleware.call_sync('datastore.config', self._datastore)['adv_login_banner'])

    @settings.fields_validator('serialport', 'serialconsole')
    async def _validate_serial(self, verrors: ValidationErrors, /, serialport: str, serialconsole: bool) -> None:
        if serialconsole:
            if not serialport:
                verrors.add(
                    'serialport',
                    'Please specify a serial port when serial console option is checked'
                )
            elif serialport not in await serial_port_choices(self):
                verrors.add(
                    'serialport',
                    'Serial port specified has not been identified by the system'
                )

            ups_port = (await self.middleware.call('ups.config')).port
            if f'/dev/{serialport}' == ups_port:
                verrors.add(
                    'serialport',
                    'Serial port must be different than the port specified for UPS Service'
                )

    @settings.fields_validator('syslogservers')
    async def _validate_syslogserver(self, verrors: ValidationErrors, /, syslogservers: list[dict[str, Any]]) -> None:
        seen_hosts = set()
        for i, server in enumerate(syslogservers):
            host = server['host']
            if host in seen_hosts:
                verrors.add(f'syslogservers.{i}.host', 'Duplicate host in syslogservers array')

            elif not re.match(r"^\[?[\w.\-:%]+]?(:\d+)?$", host):
                verrors.add(f'syslogservers.{i}.host', 'Invalid syslog server format')

            elif ']:' in host or (':' in host and ']' not in host):
                port = int(host.split(':')[-1])
                if port < 0 or port > 65535:
                    verrors.add(f'syslogservers.{i}.host', 'Port must be in the range of 0 to 65535.')

            seen_hosts.add(host)

            cert_id: int = server['tls_certificate']
            if server['transport'] == 'TLS' and cert_id:
                cert_verrors = await self.call2(
                    self.s.certificate.cert_services_validation,
                    cert_id, f'syslogservers.{i}.tls_certificate', False,
                )
                if cert_verrors:
                    verrors.extend(cert_verrors)

    @settings.fields_validator('kernel_extra_options')
    async def _validate_kernel_extra_options(self, verrors: ValidationErrors, /, kernel_extra_options: str) -> None:
        for invalid_char in ('\n', '"'):
            if invalid_char in kernel_extra_options:
                verrors.add('kernel_extra_options', f'{invalid_char!r} is an invalid character and not allowed')

        with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8") as f:
            f.write(textwrap.dedent(f"""\
                menuentry 'TrueNAS' {{
                    linux /boot/vmlinuz {kernel_extra_options}
                }}
            """))
            f.flush()

            result = await run(["grub-script-check", f.name], check=False)
            if result.returncode != 0:
                verrors.add('kernel_extra_options', 'Invalid syntax')

        invalid_param = 'systemd.unified_cgroup_hierarchy'
        if invalid_param in kernel_extra_options:
            # TODO: we don't normalize values being passed into us which allows a comical amount of potential
            #  foot-shooting
            verrors.add('kernel_extra_options', f'Modifying {invalid_param!r} is not allowed')

    @settings.fields_validator('nvidia')
    async def _validate_nvidia(self, verrors: ValidationErrors, /, nvidia: bool) -> None:
        # Only validate when nvidia is being disabled
        if nvidia is True:
            return

        container_ids = {
            device.container for device in await self.call2(
                self.s.container.device.query,
                [['attributes.dtype', '=', 'GPU'], ['attributes.gpu_type', '=', 'NVIDIA']],
            )
        }
        if containers := await self.call2(
            self.s.container.query, [['id', 'in', container_ids], ['status.state', '=', 'RUNNING']]
        ):
            verrors.add(
                'nvidia',
                f'NVIDIA GPU support cannot be disabled while the following containers are using '
                f'NVIDIA GPUs: {", ".join(c.name for c in containers)}. Please stop these containers first.'
            )

    async def do_update(self, data: SystemAdvancedUpdate) -> SystemAdvancedEntry:
        old_config = await self.config()
        old_sed = await self.sed_global_password()

        # `sed_passwd` is not a field on the entry and `consolemsg` lives in `system.general`; read both
        # side-channel values here since they are handled separately from the entry merge below.
        update = data.model_dump(expose_secrets=True)
        new_sed = update.get('sed_passwd', old_sed)

        consolemsg = None
        if 'consolemsg' in update:
            consolemsg = update['consolemsg']
            warnings.warn("`consolemsg` has been deprecated and moved to `system.general`", DeprecationWarning)

        new_config = old_config.updated(data)
        new_config = new_config.model_copy(update={
            # consolemsg lives in system.general, so it must not count as an advanced change
            'consolemsg': old_config.consolemsg,
            # a non-TLS server can't carry a client certificate
            'syslogservers': [
                server if server.transport == 'TLS' else server.model_copy(update={'tls_certificate': None})
                for server in new_config.syslogservers
            ],
        })

        await settings.validate(self, 'system_advanced_update', old_config.model_dump(), new_config.model_dump())

        if new_config != old_config or new_sed != old_sed:
            write = new_config.model_dump()
            write.pop('id', None)
            write.pop('consolemsg', None)
            write['sed_user'] = write['sed_user'].lower()
            write['sed_passwd'] = new_sed

            if not new_sed and new_sed != old_sed:
                # We want to make sure kmip uid is None in this case
                adv_kmip_uid = (await self.middleware.call(
                    'datastore.config', self._datastore, {'prefix': self._datastore_prefix}
                ))['kmip_uid']
                self.create_task(self.middleware.call('kmip.reset_sed_global_password', adv_kmip_uid))
                write['kmip_uid'] = None

            await self.middleware.call(
                'datastore.update', self._datastore, old_config.id, write, {'prefix': self._datastore_prefix}
            )

            if old_config.boot_scrub != new_config.boot_scrub:
                await (await self.call2(self.s.service.control, 'RESTART', 'cron')).wait(raise_error=True)

            generate_grub = old_config.kernel_extra_options != new_config.kernel_extra_options
            if old_config.motd != new_config.motd:
                await self.middleware.call('etc.generate', 'motd')

            if old_config.login_banner != new_config.login_banner:
                await (await self.call2(self.s.service.control, 'RELOAD', 'ssh')).wait(raise_error=True)

            if old_config.powerdaemon != new_config.powerdaemon:
                await (await self.call2(self.s.service.control, 'RESTART', 'powerd')).wait(raise_error=True)

            if syslogd_changes(old_config.model_dump(), new_config.model_dump()):
                await (await self.call2(self.s.service.control, 'RESTART', 'syslogd')).wait(raise_error=True)

            if new_sed and old_sed != new_sed:
                await self.middleware.call('kmip.sync_sed_keys')

            if new_config.kdump_enabled != old_config.kdump_enabled:
                # kdump changes require a reboot to take effect. So just generating the kdump config
                # should be enough
                await self.middleware.call('etc.generate', 'kdump')
                generate_grub = True

            if old_config.debugkernel != new_config.debugkernel:
                generate_grub = True
                # Keep the on-disk flag in sync on every transition so
                # truenas-initrd.py reads the right value on the next regen.
                await asyncio.to_thread(write_initramfs_flags, self.middleware)

            if old_config.nvidia != new_config.nvidia:
                await handle_nvidia_toggle(self)

            await configure_tty(self, old_config.model_dump(), new_config.model_dump(), generate_grub)

            if new_config.debugkernel and not old_config.debugkernel:
                await self.call2(self.s.boot.update_initramfs, BootUpdateInitramfsOptions())

        if consolemsg is not None:
            await self.middleware.call('system.general.update', {'ui_consolemsg': consolemsg})

        return await self.config()
