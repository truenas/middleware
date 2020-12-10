from middlewared.schema import accepts, Dict, Int
from middlewared.service import ConfigService
import middlewared.sqlalchemy as sa
from middlewared.validators import Range


class ReplicationConfigModel(sa.Model):
    __tablename__ = "storage_replication_config"

    id = sa.Column(sa.Integer(), primary_key=True)
    max_parallel_replication_tasks = sa.Column(sa.Integer(), nullable=True, default=None)


class ReplicationConfigService(ConfigService):

    class Config:
        namespace = "replication.config"
        datastore = "storage.replication_config"
        cli_namespace = "task.replication.config"

    @accepts(
        Dict(
            "replication_config_update",
            Int("max_parallel_replication_tasks", validators=[Range(min=1)], null=True),
            update=True,
        )
    )
    async def do_update(self, data):
        """
        `max_parallel_replication_tasks` represents a maximum number of parallel replication tasks running.
        """
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
