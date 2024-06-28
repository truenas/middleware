import os
import re
import tempfile
import textwrap
import warnings

from copy import deepcopy

import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Bool, Dict, Int, List, Patch, Password, returns, Str
from middlewared.service import ConfigService, private, no_auth_required, ValidationErrors
from middlewared.validators import Range
from middlewared.utils import run


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
    adv_syslogserver = sa.Column(sa.String(120), default='')
    adv_syslog_transport = sa.Column(sa.String(12), default='UDP')
    adv_syslog_tls_certificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    adv_syslog_tls_certificate_authority_id = sa.Column(
        sa.ForeignKey('system_certificateauthority.id'), index=True, nullable=True
    )
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

    ENTRY = Dict(
        'system_advanced_entry',
        Bool('advancedmode', required=True),
        Bool('autotune', required=True),
        Bool('kdump_enabled', required=True),
        Int('boot_scrub', validators=[Range(min_=1)], required=True),
        Bool('consolemenu', required=True),
        Bool('consolemsg', required=True),
        Bool('debugkernel', required=True),
        Bool('fqdn_syslog', required=True),
        Str('motd', required=True),
        Str('login_banner', required=True, max_length=4096),
        Bool('powerdaemon', required=True),
        Bool('serialconsole', required=True),
        Str('serialport', required=True),
        Str('anonstats_token', required=True),
        Str('serialspeed', enum=['9600', '19200', '38400', '57600', '115200'], required=True),
        Int('overprovision', validators=[Range(min_=0)], null=True, required=True),
        Bool('traceback', required=True),
        Bool('uploadcrash', required=True),
        Bool('anonstats', required=True),
        Str('sed_user', enum=['USER', 'MASTER'], required=True),
        Str('sysloglevel', enum=[
            'F_EMERG', 'F_ALERT', 'F_CRIT', 'F_ERR', 'F_WARNING', 'F_NOTICE', 'F_INFO', 'F_DEBUG',
        ], required=True),
        Str('syslogserver'),
        Str('syslog_transport', enum=['UDP', 'TCP', 'TLS'], required=True),
        Int('syslog_tls_certificate', null=True, required=True),
        Int('syslog_tls_certificate_authority', null=True, required=True),
        Bool('syslog_audit'),
        List('isolated_gpu_pci_ids', items=[Str('pci_id')], required=True),
        Str('kernel_extra_options', required=True),
        Int('id', required=True),
    )

    @private
    async def system_advanced_extend(self, data):
        data['consolemsg'] = (await self.middleware.call('system.general.config'))['ui_consolemsg']

        if data.get('sed_user'):
            data['sed_user'] = data.get('sed_user').upper()

        for k in filter(lambda k: data[k], ['syslog_tls_certificate_authority', 'syslog_tls_certificate']):
            data[k] = data[k]['id']

        data.pop('sed_passwd')
        data.pop('kmip_uid')

        return data

    async def __validate_fields(self, schema, data):
        verrors = ValidationErrors()

        serial_choice = data.get('serialport')
        if data.get('serialconsole'):
            if not serial_choice:
                verrors.add(
                    f'{schema}.serialport',
                    'Please specify a serial port when serial console option is checked'
                )
            elif serial_choice not in await self.middleware.call('system.advanced.serial_port_choices'):
                verrors.add(
                    f'{schema}.serialport',
                    'Serial port specified has not been identified by the system'
                )

        ups_port = (await self.middleware.call('ups.config'))['port']
        if not verrors and os.path.join('/dev', serial_choice or '') == ups_port:
            verrors.add(
                f'{schema}.serialport',
                'Serial port must be different then the port specified for UPS Service'
            )

        syslog_server = data.get('syslogserver')
        if syslog_server:
            match = re.match(r"^\[?[\w\.\-\:\%]+\]?(\:\d+)?$", syslog_server)
            if not match:
                verrors.add(
                    f'{schema}.syslogserver',
                    'Invalid syslog server format'
                )
            elif ']:' in syslog_server or (':' in syslog_server and not ']' in syslog_server):
                port = int(syslog_server.split(':')[-1])
                if port < 0 or port > 65535:
                    verrors.add(
                        f'{schema}.syslogserver',
                        'Port must be in the range of 0 to 65535.'
                    )

        if data['syslog_transport'] == 'TLS':
            if not data['syslog_tls_certificate_authority']:
                verrors.add(
                    f'{schema}.syslog_tls_certificate_authority', 'This is required when using TLS as syslog transport'
                )
            ca_cert = await self.middleware.call(
                'certificateauthority.query', [['id', '=', data['syslog_tls_certificate_authority']]]
            )
            if not ca_cert:
                verrors.add(f'{schema}.syslog_tls_certificate_authority', 'Unable to locate specified CA')
            elif ca_cert[0]['revoked']:
                verrors.add(f'{schema}.syslog_tls_certificate_authority', 'Specified CA has been revoked')

            if data['syslog_tls_certificate']:
                verrors.extend(await self.middleware.call(
                    'certificate.cert_services_validation', data['syslog_tls_certificate'],
                    f'{schema}.syslog_tls_certificate', False
                ))

        for invalid_char in ('\n', '"'):
            if invalid_char in data['kernel_extra_options']:
                verrors.add('kernel_extra_options', f'{invalid_char!r} is an invalid character and not allowed')

        with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8") as f:
            f.write(textwrap.dedent(f"""\
                menuentry 'TrueNAS' {{
                    linux /boot/vmlinuz {data['kernel_extra_options']}
                }}
            """))
            f.flush()

            result = await run(["grub-script-check", f.name], check=False)
            if result.returncode != 0:
                verrors.add('kernel_extra_options', 'Invalid syntax')

        invalid_param = 'systemd.unified_cgroup_hierarchy'
        if invalid_param in data['kernel_extra_options']:
            # TODO: we don't normalize values being passed into us which
            # allows a comical amount of potential foot-shooting
            verrors.add('kernel_extra_options', f'Modifying {invalid_param!r} is not allowed')

        return verrors, data

    @accepts(
        Patch(
            'system_advanced_entry', 'system_advanced_update',
            ('rm', {'name': 'id'}),
            ('rm', {'name': 'anonstats_token'}),
            ('rm', {'name': 'isolated_gpu_pci_ids'}),
            ('add', Password('sed_passwd')),
            ('attr', {'update': True}),
        )
    )
    async def do_update(self, data):
        """
        Update System Advanced Service Configuration.

        `consolemenu` should be disabled if the menu at console is not desired. It will default to standard login
        in the console if disabled.

        `autotune` when enabled executes autotune script which attempts to optimize the system based on the installed
        hardware.

        When `syslogserver` is defined, logs of `sysloglevel` or above are sent. If syslog_audit is also set
        then the remote syslog server will also receive audit messages.

        `consolemsg` is a deprecated attribute and will be removed in further releases. Please, use `consolemsg`
        attribute in the `system.general` plugin.
        """
        consolemsg = None
        if 'consolemsg' in data:
            consolemsg = data.pop('consolemsg')
            warnings.warn("`consolemsg` has been deprecated and moved to `system.general`", DeprecationWarning)

        config_data = await self.config()
        config_data['sed_passwd'] = await self.sed_global_password()
        config_data.pop('consolemsg')
        original_data = deepcopy(config_data)
        config_data.update(data)

        verrors, config_data = await self.__validate_fields('advanced_settings_update', config_data)
        verrors.check()

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
                await self.middleware.call('service.restart', 'cron')

            generate_grub = original_data['kernel_extra_options'] != config_data['kernel_extra_options']
            if original_data['motd'] != config_data['motd']:
                await self.middleware.call('etc.generate', 'motd')

            if original_data['login_banner'] != config_data['login_banner']:
                await self.middleware.call('etc.generate', 'ssh')
                await self.middleware.call('service.reload', 'ssh')

            if original_data['powerdaemon'] != config_data['powerdaemon']:
                await self.middleware.call('service.restart', 'powerd')

            if original_data['fqdn_syslog'] != config_data['fqdn_syslog']:
                await self.middleware.call('service.restart', 'syslogd')

            if (
                original_data['sysloglevel'].lower() != config_data['sysloglevel'].lower() or
                original_data['syslogserver'] != config_data['syslogserver'] or
                original_data['syslog_transport'] != config_data['syslog_transport'] or
                original_data['syslog_tls_certificate'] != config_data['syslog_tls_certificate'] or
                original_data['syslog_audit'] != config_data['syslog_audit'] or
                original_data['syslog_tls_certificate_authority'] != config_data['syslog_tls_certificate_authority']
            ):
                await self.middleware.call('service.restart', 'syslogd')

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

        if consolemsg is not None:
            await self.middleware.call('system.general.update', {'ui_consolemsg': consolemsg})

        return await self.config()

    @accepts(roles=['SYSTEM_ADVANCED_READ'])
    @returns(Bool('sed_global_password_is_set'))
    async def sed_global_password_is_set(self):
        """Returns a boolean identifying whether or not a global
        SED password has been set"""
        return bool(await self.sed_global_password())

    @accepts(roles=['SYSTEM_ADVANCED_READ'])
    @returns(Password('sed_global_password'))
    async def sed_global_password(self):
        """Returns configured global SED password in clear-text if one
        is configured, otherwise an empty string"""
        passwd = (await self.middleware.call(
            'datastore.config', 'system.advanced', {'prefix': self._config.datastore_prefix}
        ))['sed_passwd']
        return passwd if passwd else await self.middleware.call('kmip.sed_global_password')

    @accepts(roles=['SYSTEM_ADVANCED_READ'])
    @no_auth_required
    @returns(Str())
    def login_banner(self):
        """Returns user set login banner"""
        return self.middleware.call_sync('datastore.config', 'system.advanced')['adv_login_banner']
