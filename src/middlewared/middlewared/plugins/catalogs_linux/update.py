import os

from middlewared.service import CRUDService, private

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

    @private
    async def official_catalog_label(self):
        return OFFICIAL_LABEL
