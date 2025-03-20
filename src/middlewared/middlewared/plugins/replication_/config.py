from middlewared.api import api_method
from middlewared.api.current import ReplicationConfigEntry, ReplicationConfigUpdateArgs, ReplicationConfigUpdateResult

from middlewared.service import ConfigService
import middlewared.sqlalchemy as sa


class ReplicationConfigModel(sa.Model):
    __tablename__ = "storage_replication_config"

    id = sa.Column(sa.Integer(), primary_key=True)
    max_parallel_replication_tasks = sa.Column(sa.Integer(), nullable=True, default=5)


class ReplicationConfigService(ConfigService):

    class Config:
        namespace = "replication.config"
        datastore = "storage.replication_config"
        cli_namespace = "task.replication.config"
        role_prefix = "REPLICATION_TASK_CONFIG"
        entry = ReplicationConfigEntry

    @api_method(ReplicationConfigUpdateArgs, ReplicationConfigUpdateResult)
    async def do_update(self, data):
        old_config = await self.config()
        config = old_config.copy()

        config.update(data)

        await self.middleware.call(
            "datastore.update",
            self._config.datastore,
            config['id'],
            config
        )

        update = {}
        for k in config:
            if config[k] != old_config[k]:
                update[k] = config[k]
        if update:
            await self.middleware.call("zettarepl.update_config", update)

        return await self.config()
