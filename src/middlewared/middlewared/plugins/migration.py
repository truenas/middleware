import asyncio
import os

from middlewared.service import Service
import middlewared.sqlalchemy as sa
from middlewared.utils.plugins import load_modules
from middlewared.utils.python import get_middlewared_dir


def load_migrations(middleware):
    return sorted(load_modules(os.path.join(get_middlewared_dir(), "migration")), key=lambda x: x.__name__)


class MigrationModel(sa.Model):
    __tablename__ = 'system_migration'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(255), unique=True)


class MigrationService(Service):

    class Config:
        private = True

    async def run(self):
        if await self.middleware.call("keyvalue.get", "run_migration", False):
            executed_migrations = {m["name"] for m in await self.middleware.call("datastore.query", "system.migration")}

            for module in load_migrations(self.middleware):
                name = module.__name__
                if name in executed_migrations:
                    continue

                self.middleware.logger.info("Running migration %s", name)
                try:
                    if asyncio.iscoroutinefunction(module.migrate):
                        await module.migrate(self.middleware)
                    else:
                        await self.middleware.run_in_thread(module.migrate, self.middleware)
                except Exception:
                    self.middleware.logger.error("Error running migration %s", name, exc_info=True)
                    continue

                await self.middleware.call("datastore.insert", "system.migration", {"name": name}, {"ha_sync": False})

            await self.middleware.call("keyvalue.set", "run_migration", False, {"ha_sync": False})
