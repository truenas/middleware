import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import (
    SystemSecurityEntry, SystemSecurityUpdateArgs, SystemSecurityUpdateResult
)
from middlewared.plugins.failover_.enums import DisabledReasonsEnum
from middlewared.plugins.system.reboot import RebootReason
from middlewared.service import ConfigService, ValidationError, job, private
from middlewared.utils.io import set_io_uring_enabled


class SystemSecurityModel(sa.Model):
    __tablename__ = 'system_security'

    id = sa.Column(sa.Integer(), primary_key=True)
    enable_fips = sa.Column(sa.Boolean(), default=False)
    enable_gpos_stig = sa.Column(sa.Boolean(), default=False)


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

        remote_reboot_reasons = await self.middleware.call('failover.call_remote', 'system.reboot.list_reasons')
        if reason.name in remote_reboot_reasons:
            # This means the we're toggling a change in security settings but other node is
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
                'prior to enabling General Purpose OS STIG compatibiltiy mode.'
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

        if await self.middleware.call('app.query', [], {'count': True}):
            raise ValidationError(
                'system_security_update.enable_gpos_stig',
                'Apps are not supported under General Purpose OS STIG compatibility '
                'mode.'
            )

        if await self.middleware.call('virt.instance.query', [], {'count': True}):
            raise ValidationError(
                'system_security_update.enable_gpos_stig',
                'VMs are not supported under General Purpose OS STIG compatibility '
                'mode.'
            )

    @private
    async def validate(self, is_ha, ha_disabled_reasons):
        schema = 'system_security_update.enable_fips'
        if not await self.middleware.call('system.security.info.fips_available'):
            raise ValidationError(
                schema,
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

    @api_method(
        SystemSecurityUpdateArgs, SystemSecurityUpdateResult,
        audit='System security update'
    )
    @job(lock='security_update')
    async def do_update(self, job, data):
        """
        Update System Security Service Configuration.

        `enable_fips` when set, enables FIPS mode.
        `enable_gpos_stig` when set, enables compatibility with the General
        Purpose Operating System STIG.
        """
        is_ha = await self.middleware.call('failover.licensed')
        reasons = await self.middleware.call('failover.disabled.reasons')
        fips_toggled = False
        reboot_reason = None
        await self.validate(is_ha, reasons)

        old = await self.config()
        new = old.copy()
        new.update(data)
        if new == old:
            return new

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
                reboot_reason = RebootReason.STIG
                # Trigger reboot on standby to apply STIG-related configuration
                # This should only happen if user already set FIPS and is subsequently changing
                # STIG as a separate operation.
                await self.configure_security_on_ha(is_ha, job, RebootReason.GPOSSTIG)

            await self.configure_stig(new)

        if reboot_reason:
            await self.middleware.call(
                'system.reboot.toggle_reason', reboot_reason.name, reboot_reason.value
            )
        return await self.config()


async def setup(middleware):
    await middleware.call('system.security.configure_stig')
