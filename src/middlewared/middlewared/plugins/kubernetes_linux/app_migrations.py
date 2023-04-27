import asyncio
import collections
import json
import jsonschema
import os

from catalog_validation.schema.migration_schema import APP_MIGRATION_SCHEMA

from middlewared.plugins.catalogs_linux.update import OFFICIAL_LABEL
from middlewared.plugins.chart_releases_linux.utils import get_namespace
from middlewared.service import Service
from middlewared.utils.python import get_middlewared_dir


MIGRATION_MANIFEST_SCHEMA = {
    'type': 'object',
    'patternProperties': {
        '.*': {
            'type': 'array',
            'items': {'type': 'string'},
        },
    },
}
RUN_LOCK = asyncio.Lock()


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
        if not await self.middleware.call('kubernetes.validate_k8s_setup', False):
            return

        async with RUN_LOCK:
            await self.run_impl()

    async def run_impl(self):
        executed_migrations = (await self.middleware.call('k8s.app.migration.applied'))
        applied_migrations = collections.defaultdict(list)

        for catalog in await self.middleware.call('catalog.query', [['label', '=', OFFICIAL_LABEL]]):
            for migration_name, migration_data in self.load_migrations(catalog).items():
                if migration_name in (executed_migrations.get(catalog['label']) or []):
                    continue

                self.logger.info('Running kubernetes app migration %r from %r', migration_name, OFFICIAL_LABEL)
                try:
                    await self.apply_migration(catalog['label'], migration_data)
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

    async def apply_migration(self, catalog_label, migrations):
        apps = collections.defaultdict(list)
        chart_releases = await self.middleware.call('chart.release.query')
        for chart_release in chart_releases:
            apps[(chart_release['chart_metadata']['name'], chart_release['catalog_train'])].append(chart_release['id'])

        for migration in migrations:
            if migration['action'] == 'move':
                for update_app in apps[(migration['app_name'], migration['old_train'])]:
                    try:
                        await self.move_app(update_app, migration['new_train'])
                    except Exception:
                        self.logger.error(
                            'Failed to migrate %r application to %r train in %r catalog',
                            update_app, migration['new_train'], catalog_label, exc_info=True,
                        )
            elif migration['action'] == 'rename_catalog':
                for update_app in filter(lambda app: app['catalog'] == migration['old_catalog'], chart_releases):
                    try:
                        await self.move_app_to_different_catalog(update_app, migration['new_catalog'])
                    except Exception:
                        self.logger.error(
                            'Failed to migrate %r application to %r catalog',
                            update_app, migration['new_catalog'], exc_info=True,
                        )

    async def move_app(self, app_name, new_train):
        await self.middleware.call('k8s.namespace.update', get_namespace(app_name), {
            'body': {
                'metadata': {
                    'labels': {
                        'catalog_train': new_train,
                    },
                }
            }
        })

    async def move_app_to_different_catalog(self, app_name, new_catalog_name):
        await self.middleware.call('k8s.namespace.update', get_namespace(app_name), {
            'body': {
                'metadata': {
                    'labels': {
                        'catalog': new_catalog_name,
                    },
                }
            }
        })

    def load_migrations(self, catalog):
        migrations = self.official_migrations() if catalog['label'] == OFFICIAL_LABEL else {}
        migrations_path = os.path.join(catalog['location'], '.migrations')
        if os.path.isdir(migrations_path):
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
            return migrations

    def official_migrations(self):
        migrations = {}
        for migration in filter(
            lambda name: name.endswith('.json'),
            sorted(os.listdir(os.path.join(get_middlewared_dir(), 'plugins/kubernetes_linux/app_migrations')))
        ):
            with open(
                os.path.join(get_middlewared_dir(), 'plugins/kubernetes_linux/app_migrations', migration), 'r'
            ) as f:
                data = json.loads(f.read())
            migrations[migration] = data

        return migrations

    def update_migrations(self, applied_migrations):
        with open(self.migration_file_path(), 'w') as f:
            f.write(json.dumps(applied_migrations))
