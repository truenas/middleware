import asyncio
import errno
import os
import shutil

import middlewared.sqlalchemy as sa

from middlewared.schema import Bool, Dict, List, Str, ValidationErrors
from middlewared.service import accepts, CallError, CRUDService, private
from middlewared.validators import Match

from .utils import convert_repository_to_path

OFFICIAL_LABEL = 'OFFICIAL'
TMP_IX_APPS_DIR = '/tmp/ix-applications'


class CatalogModel(sa.Model):
    __tablename__ = 'services_catalog'

    label = sa.Column(sa.String(255), nullable=False, unique=True, primary_key=True)
    repository = sa.Column(sa.Text(), nullable=False)
    branch = sa.Column(sa.String(255), nullable=False)
    builtin = sa.Column(sa.Boolean(), nullable=False, default=False)
    preferred_trains = sa.Column(sa.JSON(type=list))


class CatalogService(CRUDService):

    class Config:
        datastore = 'services.catalog'
        datastore_extend = 'catalog.catalog_extend'
        datastore_extend_context = 'catalog.catalog_extend_context'
        datastore_primary_key = 'label'
        cli_namespace = 'app.catalog'

    @private
    async def catalog_extend_context(self, rows, extra):
        k8s_dataset = (await self.middleware.call('kubernetes.config'))['dataset']
        catalogs_dir = os.path.join('/mnt', k8s_dataset, 'catalogs') if k8s_dataset else f'{TMP_IX_APPS_DIR}/catalogs'
        return {
            'catalogs_dir': catalogs_dir,
            'extra': extra or {},
        }

    @private
    async def catalog_extend(self, catalog, context):
        catalog.update({
            'location': os.path.join(
                context['catalogs_dir'], convert_repository_to_path(catalog['repository'], catalog['branch'])
            ),
            'id': catalog['label'],
        })
        extra = context['extra']
        if extra.get('item_details'):
            try:
                catalog['trains'] = await self.middleware.call(
                    'catalog.items', catalog['label'], {'cache': extra.get('cache', True)},
                )
            except Exception:
                # We do not want this to fail as it will block `catalog.query` otherwise. The error would
                # already be logged as this is being called periodically as well.
                catalog.update({
                    'trains': {},
                    'healthy': False,
                })
            else:
                catalog['healthy'] = all(
                    app['healthy'] for train in catalog['trains'] for app in catalog['trains'][train].values()
                )
        return catalog

    @private
    async def common_validation(self, catalog, schema, data):
        found_trains = set(catalog['trains'])
        diff = set(data['preferred_trains']) - found_trains
        verrors = ValidationErrors()
        if diff:
            verrors.add(
                f'{schema}.preferred_trains',
                f'{", ".join(diff)} trains were not found in catalog.'
            )
        if not data['preferred_trains']:
            verrors.add(
                f'{schema}.preferred_trains',
                'At least 1 preferred train must be specified for a catalog.'
            )

        verrors.check()

    @accepts(
        Dict(
            'catalog_create',
            Bool('force', default=False),
            List('preferred_trains'),
            Str('label', required=True, empty=False, validators=[Match(r'^\w+[\w.-]*$')], max_length=60),
            Str('repository', required=True, empty=False),
            Str('branch', default='master'),
            register=True,
        )
    )
    async def do_create(self, data):
        """
        `catalog_create.preferred_trains` specifies trains which will be displayed in the UI directly for a user.
        """
        verrors = ValidationErrors()
        # We normalize the label
        data['label'] = data['label'].upper()

        if await self.query([['id', '=', data['label']]]):
            verrors.add('catalog_create.label', 'A catalog with specified label already exists', errno=errno.EEXIST)

        if await self.query([['repository', '=', data['repository']], ['branch', '=', data['branch']]]):
            for k in ('repository', 'branch'):
                verrors.add(
                    f'catalog_create.{k}', 'A catalog with same repository/branch already exists', errno=errno.EEXIST
                )

        verrors.check()

        if not data['preferred_trains']:
            data['preferred_trains'] = ['charts']

        if not data.pop('force'):
            # We will validate the catalog now to ensure it's valid wrt contents / format
            path = os.path.join(
                TMP_IX_APPS_DIR, 'validate_catalogs', convert_repository_to_path(data['repository'], data['branch'])
            )
            try:
                await self.middleware.call('catalog.update_git_repository', {**data, 'location': path}, True)
                await self.middleware.call('catalog.validate_catalog_from_path', path)
                await self.common_validation(
                    {'trains': await self.middleware.call('catalog.get_trains', path)}, 'catalog_create', data
                )
            except CallError as e:
                verrors.add('catalog_create.label', f'Failed to validate catalog: {e}')
            finally:
                await self.middleware.run_in_thread(shutil.rmtree, path, ignore_errors=True)

        verrors.check()

        await self.middleware.call('datastore.insert', self._config.datastore, data)

        asyncio.ensure_future(self.middleware.call('catalog.sync', data['label']))

        return await self.get_instance(data['label'])

    @accepts(
        Str('id'),
        Dict(
            'catalog_update',
            List('preferred_trains'),
            update=True
        )
    )
    async def do_update(self, id, data):
        catalog = await self.query([['id', '=', id]], {'extra': {'item_details': True}, 'get': True})
        await self.common_validation(catalog, 'catalog_update', data)

        await self.middleware.call('datastore.update', self._config.datastore, id, data)

        return await self.get_instance(id)

    @accepts(
        Str('id'),
    )
    def do_delete(self, id):
        catalog = self.middleware.call_sync('catalog.get_instance', id)
        if catalog['builtin']:
            raise CallError('Builtin catalogs cannot be deleted')

        ret = self.middleware.call_sync('datastore.delete', self._config.datastore, id)

        if os.path.exists(catalog['location']):
            shutil.rmtree(catalog['location'], ignore_errors=True)

        # Let's delete any unhealthy alert if we had one
        self.middleware.call_sync('alert.oneshot_delete', 'CatalogNotHealthy', id)

        return ret

    @private
    async def official_catalog_label(self):
        return OFFICIAL_LABEL
