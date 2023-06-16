import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Bool, Dict, Int, Patch
from middlewared.service import ConfigService


class SystemSecurityModel(sa.Model):
    __tablename__ = 'system_security'

    id = sa.Column(sa.Integer(), primary_key=True)
    enable_fips = sa.Column(sa.Boolean(), default=True)


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
        old = await self.config()
        new = old.copy()
        new.update(data)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            old['id'],
            new,
        )

        return await self.config()
