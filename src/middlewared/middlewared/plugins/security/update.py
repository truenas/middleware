import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Bool, Dict, Int, Patch
from middlewared.service import ConfigService, ValidationError


class SystemSecurityModel(sa.Model):
    __tablename__ = 'system_security'

    id = sa.Column(sa.Integer(), primary_key=True)
    enable_fips = sa.Column(sa.Boolean(), default=False)


class SystemSecurityService(ConfigService):

    class Config:
        cli_namespace = 'system.security'
        datastore = 'system.security'
        namespace = 'system.security'

    ENTRY = Dict(
        'system_security_entry',
        Bool('enable_fips', required=True),
        Int('id', required=True),
    )

    @accepts(
        Patch(
            'system_security_entry', 'system_security_update',
            ('rm', {'name': 'id'}),
            ('attr', {'update': True}),
        )
    )
    async def do_update(self, data):
        """
        Update System Security Service Configuration.

        `enable_fips` when set, enables FIPS mode.
        """
        if not await self.middleware.call('system.security.info.fips_available'):
            raise ValidationError(
                'system_security_update.enable_fips',
                'This feature can only be enabled on licensed iX enterprise systems. '
                'Please contact iX sales for more information.'
            )

        old = await self.config()
        new = old.copy()
        new.update(data)
        if new == old:
            return new

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            old['id'],
            new,
        )

        if new['enable_fips'] != old['enable_fips']:
            # TODO: We likely need to do some SSH magic as well
            #  let's investigate the exact configuration there
            await self.middleware.call('etc.generate', 'fips')

        return await self.config()
