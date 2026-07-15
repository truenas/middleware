from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import ReplicationConfigEntry, ReplicationConfigUpdateArgs, ReplicationConfigUpdateResult
from middlewared.service import ConfigServicePart, GenericConfigService
import middlewared.sqlalchemy as sa

if TYPE_CHECKING:
    from middlewared.main import Middleware


class ReplicationConfigModel(sa.Model):
    __tablename__ = "storage_replication_config"

    id = sa.Column(sa.Integer(), primary_key=True)
    max_parallel_replication_tasks = sa.Column(sa.Integer(), nullable=True, default=5)


class ReplicationConfigServicePart(ConfigServicePart[ReplicationConfigEntry]):
    _datastore = "storage.replication_config"
    _entry = ReplicationConfigEntry

    async def do_update(self, data: ReplicationConfigUpdateArgs) -> ReplicationConfigEntry:
        old_config = await self.config()
        new_config = old_config.updated(data)

        write = new_config.model_dump()
        write.pop("id", None)
        await self.middleware.call("datastore.update", self._datastore, old_config.id, write)

        update = {
            k: getattr(new_config, k)
            for k in new_config.model_fields
            if getattr(new_config, k) != getattr(old_config, k)
        }
        if update:
            await self.middleware.call("zettarepl.update_config", update)

        return await self.config()


class ReplicationConfigService(GenericConfigService[ReplicationConfigEntry]):
    _svc_part: ReplicationConfigServicePart

    class Config:
        namespace = "replication.config"
        datastore = "storage.replication_config"
        cli_namespace = "task.replication.config"
        role_prefix = "REPLICATION_TASK_CONFIG"
        entry = ReplicationConfigEntry
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = ReplicationConfigServicePart(self.context)

    @api_method(ReplicationConfigUpdateArgs, ReplicationConfigUpdateResult, check_annotations=True)
    async def do_update(self, data: ReplicationConfigUpdateArgs) -> ReplicationConfigEntry:
        """Update the global replication configuration shared by all replication tasks."""
        return await self._svc_part.do_update(data)
