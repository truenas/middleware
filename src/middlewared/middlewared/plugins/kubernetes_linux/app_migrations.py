import asyncio
import collections
import json
import jsonschema
import os

from middlewared.plugins.catalogs_linux.update import OFFICIAL_LABEL
from middlewared.service import CallError, Service


APP_MIGRATION_SCHEMA = {
    'type': 'array',
    'items': [{
        'type': 'object',
        'properties': {
            'old_train': {'type': 'string'},
            'app_name': {'type': 'string'},
            'new_train': {'type': 'string'},
        },
        'required': [
            'app_name',
            'new_train',
            'old_train',
        ],
    }],
}
MIGRATION_MANIFEST_SCHEMA = {
    'type': 'object',
    'patternProperties': {
        '.*': {
            'type': 'array',
            'items': [{'type': 'string'}],
        },
    },
}


class KubernetesAppMigrationsService(Service):

    MALFORMED_APP_MIGRATION = set()
    MIGRATIONS_FILE_NAME = 'app_migrations.json'

    class Config:
        namespace = 'k8s.app.migration'
        private = True

    def migration_file_path(self):
        return os.path.join(
            '/mnt', self.middleware.call_sync('kubernetes.config')['dataset'], self.MIGRATIONS_FILE_NAME
        )

    def applied(self):
        try:
            with open(self.migration_file_path(), 'r') as f:
                data = json.loads(f.read())
            jsonschema.validate(data, MIGRATION_MANIFEST_SCHEMA)
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, jsonschema.ValidationError):
            self.logger.error(
                'Malformed %r app migration file found, re-creating', self.migration_file_path(), exc_info=True
            )
        else:
            return data

        migrations = {OFFICIAL_LABEL: []}
        with open(self.migration_file_path(), 'w') as f:
            f.write(json.dumps(migrations))

        return migrations

    async def run(self):
        executed_migrations = (await self.middleware.call('k8s.app.migration.applied'))
        applied_migrations = collections.defaultdict(list)

        for catalog in await self.middleware.call('catalog.query', [['label', '=', OFFICIAL_LABEL]]):
            for migration_name, migration_data in self.load_migrations(catalog).items():
                if migration_name in (executed_migrations.get(catalog['label']) or []):
                    continue

                self.logger.info('Running kubernetes app migration %r from %r', migration_name, OFFICIAL_LABEL)
                try:
                    pass
                except Exception:
                    self.logger.error(
                        'Error running kubernetes app migration %r from %r catalog',
                        migration_name, catalog['label'], exc_info=True
                    )
                    break

                applied_migrations[catalog['label']].append(migration_name)

        for catalog, migrations in applied_migrations.items():
            if catalog in executed_migrations:
                executed_migrations[catalog].extend(migrations)
            else:
                executed_migrations[catalog] = migrations

        await self.middleware.call('k8s.app.migration.update_migrations', executed_migrations)

    def load_migrations(self, catalog):
        migrations_path = os.path.join(catalog['location'], '.migrations')
        if os.path.isdir(migrations_path):
            migrations = {}
            for migration in sorted(os.listdir(migrations_path)):
                try:
                    with open(os.path.join(migrations_path, migration), 'r') as f:
                        data = json.loads(f.read())
                    jsonschema.validate(data, APP_MIGRATION_SCHEMA)
                except (json.JSONDecodeError, jsonschema.ValidationError):
                    if (catalog['label'], migration) in self.MALFORMED_APP_MIGRATION:
                        continue

                    self.logger.error(
                        'App migration %r at %r catalog is malformed, skipping', migration, catalog['label']
                    )
                    self.MALFORMED_APP_MIGRATION.add((catalog['label'], migration))
                    continue

                migrations[migration] = data

            return migrations
        else:
            return {}

    def update_migrations(self, new_applied_migrations):
        applied_migrations = self.applied()
        applied_migrations['migrations'].extend(new_applied_migrations)
        with open(self.migration_file_path(), 'w') as f:
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
