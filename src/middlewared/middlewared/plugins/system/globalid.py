import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import SystemGlobalIDIdArgs, SystemGlobalIDIdResult
from middlewared.service import Service


class SystemGlobalID(sa.Model):
    __tablename__ = "system_globalid"
    id = sa.Column(sa.Integer(), primary_key=True)
    system_uuid = sa.Column(sa.String(32))


class SystemGlobalIDService(Service):
    class Config:
        datastore_prefix = "system_globalid"
        namespace = "system.global"
        cli_namespace = "system.global"

    @api_method(SystemGlobalIDIdArgs, SystemGlobalIDIdResult, roles=["READONLY_ADMIN"])
    async def id(self):
        """
        Retrieve a 128 bit hexadecimal UUID value unique for each TrueNAS system.
        """
        return (await self.middleware.call("datastore.config", "system.globalid"))[
            "system_uuid"
        ]
