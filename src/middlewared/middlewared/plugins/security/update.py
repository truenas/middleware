import subprocess

from middlewared.api import api_method
from middlewared.api.current import (
    SystemSecurityEntry, SystemSecurityUpdateArgs, SystemSecurityUpdateResult
)
from middlewared.plugins.failover_.enums import DisabledReasonsEnum
from middlewared.plugins.system.reboot import RebootReason
from middlewared.service import ConfigService, ValidationError, job, private
import middlewared.sqlalchemy as sa
from middlewared.utils.io import set_io_uring_enabled
from middlewared.utils.security import (
    GPOS_STIG_MIN_PASSWORD_AGE,
    GPOS_STIG_MAX_PASSWORD_AGE,
    GPOS_STIG_PASSWORD_COMPLEXITY,
    GPOS_STIG_PASSWORD_REUSE_LIMIT,
    GPOS_STIG_PASSWORD_LENGTH,
    ENTERPRISE_OPTIONS,
)


class SystemSecurityModel(sa.Model):
    __tablename__ = 'system_security'

    id = sa.Column(sa.Integer(), primary_key=True)
    enable_fips = sa.Column(sa.Boolean(), default=False)
    enable_gpos_stig = sa.Column(sa.Boolean(), default=False)
    min_password_age = sa.Column(sa.Integer(), nullable=True)
    max_password_age = sa.Column(sa.Integer(), nullable=True)
    password_complexity_ruleset = sa.Column(sa.JSON(set), nullable=True)
    min_password_length = sa.Column(sa.Integer(), nullable=True)
    password_history_length = sa.Column(sa.Integer(), nullable=True)


class SystemSecurityService(ConfigService):

    class Config:
        cli_namespace = 'system.security'
        datastore = 'system.security'
        namespace = 'system.security'
        role_prefix = 'SYSTEM_SECURITY'
        entry = SystemSecurityEntry

    @private
    async def configure_security_on_ha(self, is_ha, job, reason):
        if not is_ha:
            return

        # Send the datastore to the remote node to ensure that the
        # FIPS configuration has been synced up before reboot
        await self.middleware.call('failover.datastore.send')
        await self.middleware.call('failover.call_remote', 'etc.generate', ['fips'])
        await self.middleware.call('failover.call_remote', 'system.security.configure_stig')

        remote_reboot_reasons = await self.middleware.call('failover.call_remote', 'system.reboot.list_reasons')
        if reason.name in remote_reboot_reasons:
            # This means that we're toggling a change in security settings but other node is
            # already pending a reboot, which means the user has toggled changes twice and
            # somehow the other node didn't reboot (even though this should be automatic).
            # This is an edge case and means someone or something is doing things behind our backs
            self.logger.error('%s: reboot is already pending on other controller for same reason.', reason.name)
            await self.middleware.call('failover.call_remote', 'system.reboot.remove_reason', [reason.name])
        else:
            try:
                # we automatically reboot (and wait for) the other controller
                reboot_job = await self.middleware.call('failover.reboot.other_node')
                await job.wrap(reboot_job)
            except Exception:
                # something extravagant happened, so we'll just play it safe and say that
                # another reboot is required
                await self.middleware.call('failover.reboot.add_remote_reason', reason.name,
                                           reason.value)

    @private
    async def configure_stig(self, data=None):
        if data is None:
            data = await self.config()

        if not data['enable_gpos_stig']:
            await self.middleware.call('auth.set_authenticator_assurance_level', 'LEVEL_1')
            return

        # Per security team STIG compatibility requires that authentication methods
        # use two factors.
        await self.middleware.call('auth.set_authenticator_assurance_level', 'LEVEL_2')

        # io_uring significantly complicates ability to use auditd to monitor file
        # access and changes, and so we globally disable it when doing STIG
        # compatibility.
        await self.middleware.run_in_thread(set_io_uring_enabled, False)

        # Disable non-critical outgoing network activity
        await self.middleware.call(
            'network.configuration.update',
            {"activity": {"type": "DENY", "activities": ["usage", "update", "support"]}}
        )

    @private
    async def validate_stig(self, current_cred):
        # The following validation steps ensure that users have the ability to
        # manage the TrueNAS server after enabling STIG compatibility.
        two_factor = await self.middleware.call('auth.twofactor.config')
        if not two_factor['enabled']:
            raise ValidationError(
                'system_security_update.enable_gpos_stig',
                'Two factor authentication must be globally enabled before '
                'enabling General Purpose OS STIG compatibility mode.'
            )

        if two_factor['services']['ssh'] is False:
            raise ValidationError(
                'system_security_update.enable_gpos_stig',
                'Two factor authentication for SSH access must be enabled before '
                'enabling General Purpose OS STIG compatibility mode.'
            )

        tc_config = await self.middleware.call('truecommand.config')
        if tc_config['enabled']:
            raise ValidationError(
                'system_security_update.enable_gpos_stig',
                'TrueCommand is not supported under General Purpose OS STIG compatibility mode.'
            )

        if (await self.middleware.call('docker.config'))['pool']:
            raise ValidationError(
                'system_security_update.enable_gpos_stig',
                'Please disable Apps as Apps are not supported under General Purpose OS STIG compatibility mode.'
            )

        if (await self.middleware.call('virt.global.config'))['pool']:
            raise ValidationError(
                'system_security_update.enable_gpos_stig',
                'Please disable VMs as VMs are not supported under General Purpose OS STIG compatibility mode.'
            )

        if (await self.middleware.call('tn_connect.config'))['enabled']:
            raise ValidationError(
                'system_security_update.enable_gpos_stig',
                'Please disable TrueNAS Connect as it is not supported under '
                'General Purpose OS STIG compatibility mode.'
            )

        # We want to make sure that at least one local user account is usable
        # and has 2fa auth configured.
        two_factor_users = await self.middleware.call('user.query', [
            ['twofactor_auth_configured', '=', True],
            ['locked', '=', False],
            ['local', '=', True]
        ])

        if not two_factor_users:
            raise ValidationError(
                'system_security_update.enable_gpos_stig',
                'Two factor authentication tokens must be configured for users '
                'prior to enabling General Purpose OS STIG compatibility mode.'
            )

        if not any([user for user in two_factor_users if 'FULL_ADMIN' in user['roles']]):
            raise ValidationError(
                'system_security_update.enable_gpos_stig',
                'At least one local user with full admin privileges must be '
                'configured with a two factor authentication token prior to enabling '
                'General Purpose OS STIG compatibility mode.'
            )

        if current_cred and current_cred.is_user_session and '2FA' not in current_cred.user['account_attributes']:
            # We need to do everything we can to make sure that 2FA is _actually_ working for
            # an account to which admin has access.
            raise ValidationError(
                'system_security_update.enable_gpos_stig',
                'Credential used to enable General Purpose OS STIG compatibility '
                'must have two factor authentication enabled, and have used two factor '
                'authentication for the currently-authenticated session.'
            )

        excluded_admins = [
            user['username'] for user in await self.middleware.call(
                'user.query', [
                    ["immutable", "=", True], ["password_disabled", "=", False],
                    ["locked", "=", False], ["unixhash", "!=", "*"],
                    ["local", "=", True]
                ],
            )
        ]

        if excluded_admins:
            # For STIG compatibility, all general purpose administrative accounts,
            # e.g. 'root' and 'truenas_admin', cannot use password login.  (SRG-OS-000109-GPOS-00056)
            raise ValidationError(
                'system_security_update.enable_gpos_stig',
                'General purpose administrative accounts with password authentication are '
                'not compatible with STIG compatibility mode.  '
                f'PLEASE DISABLE PASSWORD AUTHENTICATION ON THE FOLLOWING ACCOUNTS: {", ".join(excluded_admins)}.'
            )

    @private
    async def validate(self, is_ha, new, ha_disabled_reasons):
        schema = 'system_security_update.enable_fips'

        if not await self.middleware.call('system.security.info.fips_available'):
            for key in new.keys():
                if key not in ENTERPRISE_OPTIONS or not new[key]:
                    continue

                raise ValidationError(
                    f'system_security_update.{key}',
                    'This feature can only be enabled on licensed iX enterprise systems. '
                    'Please contact iX sales for more information.'
                )

        if is_ha and ha_disabled_reasons:
            bad_reasons = set(ha_disabled_reasons) - {
                DisabledReasonsEnum.LOC_FIPS_REBOOT_REQ.name,
                DisabledReasonsEnum.REM_FIPS_REBOOT_REQ.name,
            }
            if bad_reasons:
                formatted = '\n'.join([DisabledReasonsEnum[i].value for i in bad_reasons])
                raise ValidationError(
                    schema,
                    f'Security settings cannot be updated while HA is in an unhealthy state: ({formatted})'
                )

    @private
    async def validate_password_security(self, old: dict, new: dict) -> bool:
        """
        Performs validation of global local account security settings.

        returns boolean indicating that we need to reload local users after applying settings
        """
        combined = old | new
        if new['enable_gpos_stig']:
            # For convenience we'll override defaults when GPOS STIG is enabled

            # SRG-OS-000073-GPOS-00041
            # GPOS STIG requires a min_password_age to be set to 1 day
            # Increasing beyond this represents a stricter standard.
            new['min_password_age'] = combined['min_password_age'] or GPOS_STIG_MIN_PASSWORD_AGE

            # SRG-OS-000076-GPOS-00044
            # Operating systems must enforce a 60-day maximum password lifetime restriction.
            # Decreasing below this represents a stricter standard.
            new['max_password_age'] = combined['max_password_age'] or GPOS_STIG_MAX_PASSWORD_AGE
            if new['max_password_age'] > GPOS_STIG_MAX_PASSWORD_AGE:
                raise ValidationError(
                    'system_security_update.max_password_age',
                    f'{new["max_password_age"]}: Maximum password age must be less than or equal to '
                    f'{GPOS_STIG_MAX_PASSWORD_AGE} days in GPOS STIG compatibility mode.'
                )

            # SRG-OS-000077-GPOS-00045
            # Prohibit reuse for minimum of 5 generations
            # Increasing beyond this represents a stricter standard
            new['password_history_length'] = combined['password_history_length'] or GPOS_STIG_PASSWORD_REUSE_LIMIT
            if new['password_history_length'] < GPOS_STIG_PASSWORD_REUSE_LIMIT:
                raise ValidationError(
                    'system_security_update.password_history_length',
                    'GPOS STIG compatibility requires that password reuse be '
                    'limited for a minimum of five generations.'
                )

            # SRG-OS-000069-GPOS-00037
            # SRG-OS-000070-GPOS-00038
            # SRG-OS-000071-GPOS-00039
            # SRG-OS-000266-GPOS-00101
            # Passwords must contain at least one lowercase character, one lowercase character,
            # one number, and one special character.
            ruleset = combined['password_complexity_ruleset'] or set(GPOS_STIG_PASSWORD_COMPLEXITY)
            new['password_complexity_ruleset'] = ruleset
            if missing := GPOS_STIG_PASSWORD_COMPLEXITY - new['password_complexity_ruleset']:
                raise ValidationError(
                    'system_security_update.password_complexity_ruleset',
                    'GPOS STIG compatibility requires the following password complexity '
                    f'rules: {", ".join(missing)}'
                )

            new['min_password_length'] = combined['min_password_length'] or GPOS_STIG_PASSWORD_LENGTH
            if new['min_password_length'] < GPOS_STIG_PASSWORD_LENGTH:
                raise ValidationError(
                    'system_security_update.min_password_length',
                    'GPOS STIG compatibility requires password lengths of at least 15 characters.'
                )

        # The following keys determine whether we need to rewrite our shadow file
        # At some point if we decide to plumb through password changes via pam / middleware
        # we can add password warn and password inactivity fields
        if all([old[key] == new[key] for key in (
            'min_password_age',
            'max_password_age',
        )]):
            return False

        if new['min_password_age'] is not None and new['max_password_age'] is not None:
            if new['min_password_age'] >= new['max_password_age']:
                raise ValidationError(
                    'system_security_update.min_password_age',
                    'Minimum password age must be lower than the maximum password age in '
                    'order to allow users to change their passwords.'
                )

        if new['max_password_age'] is not None and new['max_password_age'] < 7:
            # Setting max password age to less than 7 days runs very high risk
            # of admins accidentally locking themselves out
            raise ValidationError(
                'system_security_update.max_password_age',
                'Maximum password age may not be set to a value of less than 7 days.'
            )

        return True

    @api_method(
        SystemSecurityUpdateArgs, SystemSecurityUpdateResult,
        audit='System security update'
    )
    @job(lock='security_update')
    async def do_update(self, job, data):
        """
        Update System Security Service Configuration.

        This method is used to change the FIPS, STIG, and local account
        policies for TrueNAS Enterprise. These features are not
        available in community editions of TrueNAS.
        """
        is_ha = await self.middleware.call('failover.licensed')
        reasons = await self.middleware.call('failover.disabled.reasons')
        fips_toggled = False
        reboot_reason = None

        old = await self.config()
        new = old.copy()
        new.update(data)
        if new == old:
            return new

        await self.validate(is_ha, new, reasons)

        must_update_account_policy = await self.validate_password_security(old, new)

        if new['enable_gpos_stig']:
            if not new['enable_fips']:
                raise ValidationError(
                    'system_security_update.enable_gpos_stig',
                    'FIPS mode is required in General Purpose OS STIG compatibility mode.'
                )

            await self.validate_stig(job.credentials)

        await self.middleware.call('datastore.update', self._config.datastore, old['id'], new)

        if new['enable_fips'] != old['enable_fips']:
            # TODO: We likely need to do some SSH magic as well
            #  let's investigate the exact configuration there
            reboot_reason = RebootReason.FIPS
            await self.middleware.call('etc.generate', 'fips')
            await self.configure_security_on_ha(is_ha, job, RebootReason.FIPS)
            fips_toggled = True

        if new['enable_gpos_stig'] != old['enable_gpos_stig']:
            if not fips_toggled:
                reboot_reason = RebootReason.GPOSSTIG
                # Trigger reboot on standby to apply STIG-related configuration
                # This should only happen if user already set FIPS and is subsequently changing
                # STIG as a separate operation.
                await self.configure_security_on_ha(is_ha, job, RebootReason.GPOSSTIG)

            await self.configure_stig(new)

        if reboot_reason:
            await self.middleware.call(
                'system.reboot.toggle_reason', reboot_reason.name, reboot_reason.value
            )

        if must_update_account_policy:
            await self.middleware.call('etc.generate', 'shadow')
            await self.middleware.call('smb.apply_account_policy')

        return await self.config()

    @private
    def configure_fips(self, database_path=None):
        args = ['configure_fips']
        if database_path is not None:
            args.append(database_path)

        try:
            p = subprocess.run(args, capture_output=True, check=True, encoding='utf-8', errors='ignore')
            output = p.stderr.strip()
            if output:
                self.logger.error('configure_fips output:\n%s', output)
        except subprocess.CalledProcessError as e:
            self.logger.error('configure_fips error:\n%s', e.stderr)
            raise


async def on_config_upload(middleware, path):
    await middleware.call('system.security.configure_fips', path)


async def setup(middleware):
    middleware.register_hook('config.on_upload', on_config_upload, sync=True)

    await middleware.call('system.security.configure_stig')
