import asyncio
import json
import jsonschema
import os

from middlewared.service import CallError, Service
from middlewared.utils.plugins import load_modules
from middlewared.utils.python import get_middlewared_dir


MIGRATION_MANIFEST_SCHEMA = {
    'type': 'object',
    'properties': {
        'migrations': {
            'type': 'array',
            'items': [{'type': 'string'}],
        },
    },
    'required': [
        'migrations',
    ],
}


def load_migrations():
    return sorted(load_modules(
        os.path.join(get_middlewared_dir(), 'plugins/kubernetes_linux/migrations')
    ), key=lambda x: x.__name__)


class KubernetesMigrationsService(Service):

    MIGRATIONS_FILE_NAME = 'migrations.json'

    class Config:
        namespace = 'k8s.migration'
        private = True

    @property
    def migration_file_path(self):
        return os.path.join(
            '/mnt', self.middleware.call_sync('kubernetes.config')['dataset'], self.MIGRATIONS_FILE_NAME
        )

    def applied(self):
        try:
            with open(self.migration_file_path, 'r') as f:
                data = json.loads(f.read())
            jsonschema.validate(data, MIGRATION_MANIFEST_SCHEMA)
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, jsonschema.ValidationError):
            self.logger.error('Malformed %r migration file found, re-creating', self.migration_file_path, exc_info=True)

        migrations = {'migrations': []}
        with open(self.migration_file_path, 'w') as f:
            f.write(json.dumps(migrations))

        return migrations

    async def run(self):
        executed_migrations = (await self.middleware.call('k8s.migration.applied'))['migrations']
        applied_migrations = []

        for module in load_migrations():
            name = module.__name__
            if name in executed_migrations:
                continue

            self.logger.info('Running kubernetes migration %r', name)
            try:
                if asyncio.iscoroutinefunction(module.migrate):
                    await module.migrate(self.middleware)
                else:
                    await self.middleware.run_in_thread(module.migrate, self.middleware)
            except Exception:
                self.logger.error('Error running kubernetes migration %r', name, exc_info=True)
                break

            applied_migrations.append(name)

        await self.middleware.call('k8s.migration.update_migrations', applied_migrations)

    def update_migrations(self, new_applied_migrations):
        applied_migrations = self.applied()
        applied_migrations['migrations'].extend(new_applied_migrations)
        with open(self.migration_file_path, 'w') as f:
            f.write(json.dumps(applied_migrations))

    def scale_version_check(self):
        available_migrations = [module.__name__ for module in load_migrations()]
        unavailable_ones = [
            applied for applied in self.applied()['migrations'] if applied not in available_migrations
        ]
        if unavailable_ones:
            raise CallError(
                'SCALE version does not contain already applied kubernetes '
                f'migrations ( {", ".join(unavailable_ones)!r} )'
            )
