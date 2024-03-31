import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Dict, Int, returns, Str
from middlewared.service import Service


class SystemGlobalID(sa.Model):
    __tablename__ = 'system_globalid'

    id = sa.Column(sa.Integer(), primary_key=True)
    system_uuid = sa.Column(sa.String(32))


class SystemGlobalIDService(Service):
    class Config:
        datastore_prefix = 'system_globalid'
        namespace = 'system.global'
        cli_namespace = 'system.global'

    ENTRY = Dict(
        'system_globalid_entry',
        Int('id'),
        Str('system_uuid', required=True),
        register=True
    )

    @accepts(roles=['READONLY_ADMIN'])
    @returns(Str('system_uuid'))
    async def id(self):
        """
        Retrieve a 128 bit hexadecimal UUID value unique for each TrueNAS system.
        """
        return (await self.middleware.call('datastore.config', 'system.globalid'))['system_uuid']
