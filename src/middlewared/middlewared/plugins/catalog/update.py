import os

import middlewared.sqlalchemy as sa

from middlewared.plugins.docker.state_utils import catalog_ds_path
from middlewared.schema import accepts, Dict, List, Str
from middlewared.service import ConfigService, private, ValidationErrors
from middlewared.validators import Match

from .git_utils import convert_repository_to_path
from .utils import (
    OFFICIAL_CATALOG_BRANCH, OFFICIAL_CATALOG_REPO, OFFICIAL_ENTERPRISE_TRAIN, OFFICIAL_LABEL, TMP_IX_APPS_CATALOGS
)

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

    ENTRY = Dict(
            'catalog_create',
            List('preferred_trains'),
            Str('id'),
            Str(
                'label', required=True, validators=[Match(
                    r'^\w+[\w.-]*$',
                    explanation='Label must start with an alphanumeric character and can include dots and dashes.'
                )],
                max_length=60,
            ),
            register=True,
        )

    @private
    def extend(self, data, context):
        data.update({
            'id': data['label'],
            'location': os.path.join(
                context['catalog_dir'], convert_repository_to_path(OFFICIAL_CATALOG_REPO, OFFICIAL_CATALOG_BRANCH)
            ),
        })
        return data

    @private
    async def extend_context(self, rows, extra):
        if await self.dataset_mounted():
            catalog_dir = catalog_ds_path((await self.middleware.call('docker.config'))['dataset'])
        else:
            # FIXME: This can eat lots of memory if it's a large catalog
            catalog_dir = TMP_IX_APPS_CATALOGS

        return {
            'catalog_dir': catalog_dir,
        }

    @private
    async def dataset_mounted(self):
        if docker_ds := (await self.middleware.call('docker.config'))['dataset']:
            return bool(await self.middleware.call(
                'filesystem.mount_info', [
                    ['mount_source', '=', os.path.join(docker_ds, 'catalogs')], ['fs_type', '=', 'zfs'],
                ],
            ))

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
            await self.middleware.call('system.product_type') == 'SCALE_ENTERPRISE' and
            OFFICIAL_ENTERPRISE_TRAIN not in data['preferred_trains']
        ):
            verrors.add(
                f'{schema}.preferred_trains',
                f'Enterprise systems must at least have {OFFICIAL_ENTERPRISE_TRAIN!r} train enabled'
            )

        verrors.check()

    @accepts(
        Dict(
            'catalog_update',
            List('preferred_trains'),
            update=True
        )
    )
    async def do_update(self, data):
        """
        Update catalog preferences.
        """
        await self.common_validation('catalog_update', data)

        await self.middleware.call('datastore.update', self._config.datastore, OFFICIAL_LABEL, data)

        return await self.config()
