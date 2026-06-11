from __future__ import annotations

from middlewared.api.current import ReportingEntry, ReportingUpdate
from middlewared.service import ConfigServicePart
import middlewared.sqlalchemy as sa


class ReportingModel(sa.Model):
    __tablename__ = "reporting"

    id = sa.Column(sa.Integer(), primary_key=True)
    tier0_days = sa.Column(sa.Integer(), default=7)
    tier1_days = sa.Column(sa.Integer(), default=30)
    tier1_update_interval = sa.Column(sa.Integer(), default=300)  # This is in seconds


class ReportingConfigServicePart(ConfigServicePart[ReportingEntry]):
    _datastore = "reporting"
    _entry = ReportingEntry

    async def do_update(self, data: ReportingUpdate) -> ReportingEntry:
        old = await self.config()
        new = old.updated(data)
        await self._update(new)
        await (await self.middleware.call("service.control", "RESTART", "netdata")).wait(raise_error=True)
        return await self.config()
