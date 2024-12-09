import middlewared.sqlalchemy as sa

from middlewared.api.common import SystemSecurityEntry, SystemSecurityUpdateArgs, SystemSecurityUpdateResult
from middlewared.service import ConfigService, ValidationError, ValidationErrors


class SystemSecurityModel(sa.Model):
    __tablename__ = 'system_security'

    id = sa.Column(sa.Integer(), primary_key=True)
    stig_enabled = sa.Column(sa.Boolean(), default=False)



class SystemSecurityService(ConfigService):

    class Config:
        datastore = 'system.security'
        entry = SystemSecurityEntry
        role = 'SYSTEM_SECURITY'


    async def apply(self):
        if not (await self.config())['stig_enabled']:
            await self.middleware.call('auth.set_authenticator_assurance_level', 'LEVEL_1')
            return

        await self.middleware.call('auth.set_authenticator_assurance_level', 'LEVEL_2')

    async def common_validation(self, data, verrors):
        # For now simply short-circuit validation if we're turning off STIG mode
        if not data['stig_enabled']:
            return

        two_factor = await self.middleware.call('auth.twofactor.config')
        if not two_factor['enabled']:
            verrors.add(
                 'system_security_update.stig_enabled',
                 'Two factor authentication must be globally enabled before '
                 'enabling STIG compatibility mode.'
            )

        two_factor_users = await self.middleware.call('user.query', [
            'twofactor_auth_configured', '=', True
        ])

        if not two_factor_users:
            verrors.add(
                'system_security_update.stig_enabled',
                'Two factor authentication tokens must be configured for users '
                'prior to enabling STIG compatibiltiy mode.'
            )

        # We really want to make sure the administrator has ability to administer
        # the server.
        if not any([user for user in two_factor_users if 'FULL_ADMIN' in user['roles'] and user['local']]):
            verrors.add(
                'system_security_update.stig_enabled',
                'At least one local user with full admin privileges and must be '
                'configured with a two factor authentication token prior to enabling '
                'STIG compatibility mode.'
            )


        if not await self.middleware.call('system.is_enterprise'):
            verrors.add(
                'system_security_update.stig_enabled',
                'STIG compatibility mode is only available for enterprise-licensed '
                'TrueNAS servers.'
            )

    @api_method(
        SystemSecurityUpdateArgs, SystemSecurityUpdateResult
        audit='System security update:'
    )
    async def do_update(self, data):
        old = await self.config()
        new = old | data

        verrors = ValidationErrors()
        await self.common_validation(new, verrors)
        verrors.check()

        await self.middleware.call('datastore.update', new['id'], new)

        await self.apply()
        return await self.config()
