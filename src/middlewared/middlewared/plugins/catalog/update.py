import os

import middlewared.sqlalchemy as sa

from middlewared.api import api_method
from middlewared.api.current import (
    CatalogEntry, CatalogUpdateArgs, CatalogUpdateResult, CatalogTrainsArgs, CatalogTrainsResult,
)
from middlewared.plugins.docker.state_utils import catalog_ds_path, CATALOG_DATASET_NAME
from middlewared.service import ConfigService, private, ValidationErrors
from middlewared.utils import ProductType

from .utils import OFFICIAL_ENTERPRISE_TRAIN, OFFICIAL_LABEL, TMP_IX_APPS_CATALOGS


class CatalogModel(sa.Model):
    __tablename__ = 'services_catalog'

    label = sa.Column(sa.String(255), nullable=False, unique=True, primary_key=True)
    preferred_trains = sa.Column(sa.JSON(list))


class CatalogService(ConfigService):

    class Config:
        datastore = 'services.catalog'
        datastore_extend = 'catalog.extend'
        datastore_extend_context = 'catalog.extend_context'
        datastore_primary_key = 'label'
        datastore_primary_key_type = 'string'
        cli_namespace = 'app.catalog'
        namespace = 'catalog'
        role_prefix = 'CATALOG'
        entry = CatalogEntry

    @private
    def extend(self, data, context):
        data.update({
            'id': data['label'],
            'location': context['catalog_dir'],
        })
        return data

    @api_method(CatalogTrainsArgs, CatalogTrainsResult, roles=['CATALOG_READ'])
    async def trains(self):
        """
        Retrieve available trains.
        """
        return list(await self.middleware.call('catalog.apps', {'cache': True, 'cache_only': True}))

    @private
    async def extend_context(self, rows, extra):
        if await self.dataset_mounted():
            catalog_dir = catalog_ds_path()
        else:
            # FIXME: This can eat lots of memory if it's a large catalog
            catalog_dir = TMP_IX_APPS_CATALOGS

        return {
            'catalog_dir': catalog_dir,
        }

    @private
    async def dataset_mounted(self):
        if docker_ds := (await self.middleware.call('docker.config'))['dataset']:
            expected_source = os.path.join(docker_ds, CATALOG_DATASET_NAME)
            catalog_path = catalog_ds_path()
            try:
                sfs = await self.middleware.call('filesystem.statfs', catalog_path)
                return sfs['source'] == expected_source and sfs['fstype'] == 'zfs'
            except Exception:
                return False

        return False

    @private
    async def common_validation(self, schema, data):
        verrors = ValidationErrors()
        if not data['preferred_trains']:
            verrors.add(
                f'{schema}.preferred_trains',
                'At least 1 preferred train must be specified.'
            )
        if (
            await self.middleware.call('system.product_type') == ProductType.ENTERPRISE and
            OFFICIAL_ENTERPRISE_TRAIN not in data['preferred_trains']
        ):
            verrors.add(
                f'{schema}.preferred_trains',
                f'Enterprise systems must at least have {OFFICIAL_ENTERPRISE_TRAIN!r} train enabled'
            )

        verrors.check()

    @api_method(CatalogUpdateArgs, CatalogUpdateResult)
    async def do_update(self, data):
        """
        Update catalog preferences.
        """
        await self.common_validation('catalog_update', data)

        await self.middleware.call('datastore.update', self._config.datastore, OFFICIAL_LABEL, data)

        return await self.config()

    @private
    async def update_train_for_enterprise(self):
        catalog = await self.middleware.call('catalog.config')
        if await self.middleware.call('system.product_type') == ProductType.ENTERPRISE:
            preferred_trains = []
            # Logic coming from here
            # https://github.com/truenas/middleware/blob/e7f2b29b6ff8fadcc9fdd8d7f104cbbf5172fc5a/src/middlewared
            # /middlewared/plugins/catalogs_linux/update.py#L341
            can_have_multiple_trains = not await self.middleware.call('system.is_ha_capable') and not (
                await self.middleware.call('failover.hardware')
            ).startswith('TRUENAS-R')
            if OFFICIAL_ENTERPRISE_TRAIN not in catalog['preferred_trains'] and can_have_multiple_trains:
                preferred_trains = catalog['preferred_trains'] + [OFFICIAL_ENTERPRISE_TRAIN]
            elif not can_have_multiple_trains:
                preferred_trains = [OFFICIAL_ENTERPRISE_TRAIN]

            if preferred_trains:
                await self.middleware.call(
                    'datastore.update', self._config.datastore, OFFICIAL_LABEL, {
                        'preferred_trains': preferred_trains,
                    },
                )


async def enterprise_train_update(middleware, *args, **kwargs):
    await middleware.call('catalog.update_train_for_enterprise')


async def setup(middleware):
    middleware.register_hook('system.post_license_update', enterprise_train_update)
