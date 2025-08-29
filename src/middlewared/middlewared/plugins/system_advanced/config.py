import re
import tempfile
import textwrap
import warnings

from copy import deepcopy

import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import (
    SystemAdvancedEntry, SystemAdvancedLoginBannerArgs, SystemAdvancedLoginBannerResult,
    SystemAdvancedSedGlobalPasswordArgs, SystemAdvancedSedGlobalPasswordResult,
    SystemAdvancedSedGlobalPasswordIsSetArgs, SystemAdvancedSedGlobalPasswordIsSetResult, SystemAdvancedUpdateArgs,
    SystemAdvancedUpdateResult
)
from middlewared.service import ConfigService, private
from middlewared.utils import run
from middlewared.utils.service.settings import SettingsHelper

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
    adv_isolated_gpu_pci_ids = sa.Column(sa.JSON(), default=[])
    adv_kernel_extra_options = sa.Column(sa.Text(), default='', nullable=False)


class SystemAdvancedService(ConfigService):

    class Config:
        datastore = 'system.advanced'
        datastore_prefix = 'adv_'
        datastore_extend = 'system.advanced.system_advanced_extend'
        namespace = 'system.advanced'
        cli_namespace = 'system.advanced'
        role_prefix = 'SYSTEM_ADVANCED'
        entry = SystemAdvancedEntry

    @private
    async def system_advanced_extend(self, data):
        data['consolemsg'] = (await self.middleware.call('system.general.config'))['ui_consolemsg']

        if data.get('sed_user'):
            data['sed_user'] = data.get('sed_user').upper()

        data.pop('sed_passwd')
        data.pop('kmip_uid')

        return data

    @settings.fields_validator('serialport', 'serialconsole')
    async def _validate_serial(self, verrors, serialport, serialconsole):
        if serialconsole:
            if not serialport:
                verrors.add(
                    'serialport',
                    'Please specify a serial port when serial console option is checked'
                )
            elif serialport not in await self.middleware.call('system.advanced.serial_port_choices'):
                verrors.add(
                    'serialport',
                    'Serial port specified has not been identified by the system'
                )

            ups_port = (await self.middleware.call('ups.config'))['port']
            if f'/dev/{serialport}' == ups_port:
                verrors.add(
                    'serialport',
                    'Serial port must be different than the port specified for UPS Service'
                )

    @settings.fields_validator('syslogservers')
    async def _validate_syslogserver(self, verrors, syslogservers):
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

            cert_id = server['tls_certificate']
            if server['transport'] == 'TLS' and cert_id:
                verrors.extend(
                    await self.middleware.call(
                        'certificate.cert_services_validation', cert_id, f'syslogservers.{i}.tls_certificate', False
                    )
                )

    @settings.fields_validator('kernel_extra_options')
    async def _validate_kernel_extra_options(self, verrors, kernel_extra_options):
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

    def _syslogd_changes(self, orig_config: dict, new_config: dict) -> bool:
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

    @api_method(SystemAdvancedUpdateArgs, SystemAdvancedUpdateResult, audit='System advanced update')
    async def do_update(self, data):
        """
        Update System Advanced Service Configuration.
        """
        consolemsg = None
        if 'consolemsg' in data:
            consolemsg = data.pop('consolemsg')
            warnings.warn("`consolemsg` has been deprecated and moved to `system.general`", DeprecationWarning)

        for server in data.get('syslogservers', []):
            if server['transport'] != 'TLS':
                server['tls_certificate'] = None

        config_data = await self.config()
        config_data['sed_passwd'] = await self.sed_global_password()
        config_data.pop('consolemsg')
        original_data = deepcopy(config_data)
        config_data.update(data)

        await settings.validate(self, 'system_advanced_update', original_data, config_data)

        if config_data != original_data:
            if original_data.get('sed_user'):
                original_data['sed_user'] = original_data['sed_user'].lower()
            if config_data.get('sed_user'):
                config_data['sed_user'] = config_data['sed_user'].lower()
            if not config_data['sed_passwd'] and config_data['sed_passwd'] != original_data['sed_passwd']:
                # We want to make sure kmip uid is None in this case
                adv_config = await self.middleware.call('datastore.config', self._config.datastore)
                self.middleware.create_task(
                    self.middleware.call('kmip.reset_sed_global_password', adv_config['adv_kmip_uid'])
                )
                config_data['kmip_uid'] = None

            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                config_data['id'],
                config_data,
                {'prefix': self._config.datastore_prefix}
            )

            if original_data['boot_scrub'] != config_data['boot_scrub']:
                await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)

            generate_grub = original_data['kernel_extra_options'] != config_data['kernel_extra_options']
            if original_data['motd'] != config_data['motd']:
                await self.middleware.call('etc.generate', 'motd')

            if original_data['login_banner'] != config_data['login_banner']:
                await (await self.middleware.call('service.control', 'RELOAD', 'ssh')).wait(raise_error=True)

            if original_data['powerdaemon'] != config_data['powerdaemon']:
                await (await self.middleware.call('service.control', 'RESTART', 'powerd')).wait(raise_error=True)

            if self._syslogd_changes(original_data, config_data):
                await (await self.middleware.call('service.control', 'RESTART', 'syslogd')).wait(raise_error=True)

            if config_data['sed_passwd'] and original_data['sed_passwd'] != config_data['sed_passwd']:
                await self.middleware.call('kmip.sync_sed_keys')

            if config_data['kdump_enabled'] != original_data['kdump_enabled']:
                # kdump changes require a reboot to take effect. So just generating the kdump config
                # should be enough
                await self.middleware.call('etc.generate', 'kdump')
                generate_grub = True

            if original_data['debugkernel'] != config_data['debugkernel']:
                generate_grub = True

            await self.middleware.call('system.advanced.configure_tty', original_data, config_data, generate_grub)

            if config_data['debugkernel'] and not original_data['debugkernel']:
                await self.middleware.call('boot.update_initramfs')

        if consolemsg is not None:
            await self.middleware.call('system.general.update', {'ui_consolemsg': consolemsg})

        return await self.config()

    @api_method(
        SystemAdvancedSedGlobalPasswordIsSetArgs,
        SystemAdvancedSedGlobalPasswordIsSetResult,
        roles=['SYSTEM_ADVANCED_READ']
    )
    async def sed_global_password_is_set(self):
        """Returns a boolean identifying whether or not a global
        SED password has been set"""
        return bool(await self.sed_global_password())

    @api_method(
        SystemAdvancedSedGlobalPasswordArgs,
        SystemAdvancedSedGlobalPasswordResult,
        roles=['SYSTEM_ADVANCED_READ']
    )
    async def sed_global_password(self):
        """Returns configured global SED password in clear-text if one
        is configured, otherwise an empty string"""
        passwd = (await self.middleware.call(
            'datastore.config', 'system.advanced', {'prefix': self._config.datastore_prefix}
        ))['sed_passwd']
        return passwd if passwd else await self.middleware.call('kmip.sed_global_password')

    @api_method(SystemAdvancedLoginBannerArgs, SystemAdvancedLoginBannerResult, authentication_required=False)
    def login_banner(self):
        """Returns user set login banner"""
        # NOTE: This endpoint doesn't require authentication because
        # it is used by UI on the login page
        return self.middleware.call_sync('datastore.config', 'system.advanced')['adv_login_banner']
