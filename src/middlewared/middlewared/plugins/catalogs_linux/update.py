import errno
import os

from middlewared.schema import Dict, Str, ValidationErrors
from middlewared.service import accepts, CRUDService, private

from .utils import convert_repository_to_path

OFFICIAL_LABEL = 'OFFICIAL'


class CatalogService(CRUDService):

    class Config:
        datastore = 'services.catalog'
        datastore_extend = 'catalog.catalog_extend'
        datastore_extend_context = 'catalog.catalog_extend_context'
        cli_namespace = 'app.catalog'

    @private
    async def catalog_extend_context(self, extra):
        k8s_dataset = (await self.middleware.call('kubernetes.config'))['dataset']
        catalogs_dir = os.path.join('/mnt', k8s_dataset, 'catalogs') if k8s_dataset else '/tmp/ix-applications/catalogs'
        return {
            'catalogs_dir': catalogs_dir,
            'extra': extra or {},
        }

    @private
    async def catalog_extend(self, catalog, context):
        catalog.update({
            'location': os.path.join(context['catalogs_dir'], convert_repository_to_path(catalog['repository'])),
            'id': catalog['label'].upper(),
        })
        extra = context['extra']
        if extra.get('item_details'):
            catalog['trains'] = await self.middleware.call(
                'catalog.items', catalog['label'], {'cache': extra.get('cache', True)},
            )
        return catalog

    @accepts(
        Dict(
            'catalog_create',
            Str('label', required=True, empty=False),
            Str('repository', required=True, empty=False),
            Str('branch', default='master'),
        )
    )
    async def do_create(self, data):
        verrors = ValidationErrors()
        if await self.query([['id', '=', data['label']]]):
            verrors.add('catalog_create.label', 'A catalog with specified label already exists', errno=errno.EEXIST)

        if await self.query([['repository', '=', data['repository']], ['branch', '=', data['branch']]]):
            for k in ('repository', 'branch'):
                verrors.add(
                    f'catalog_create.{k}', 'A catalog with same repository/branch already exists', errno=errno.EEXIST
                )

        await self.middleware.call('datastore.insert', self._config.datastore, data)

        return await self.get_instance(data['label'])

    @private
    async def official_catalog_label(self):
        return OFFICIAL_LABEL

    # TODO: Please see if there are edge cases with deletion/updating catalogs for already installed apps of those catalogs
