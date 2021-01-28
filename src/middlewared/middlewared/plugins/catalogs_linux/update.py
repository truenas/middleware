import os

from copy import deepcopy

from middlewared.service import CRUDService, filterable, private
from middlewared.utils import filter_list

from .utils import convert_repository_to_path

OFFICIAL_LABEL = 'OFFICIAL'
CATALOGS = [
    {
        'label': OFFICIAL_LABEL,
        'repository': 'https://github.com/truenas/charts.git',
        'branch': 'master',
    }
]


class CatalogService(CRUDService):

    @filterable
    async def query(self, filters, options):
        """
        Query available catalogs.

        `options.extra.item_details` is a boolean value which if set will retrieve items details for each chart.
        """
        options = options or {}
        extra = options.get('extra', {})
        catalogs = deepcopy(CATALOGS)
        k8s_dataset = (await self.middleware.call('kubernetes.config'))['dataset']
        catalogs_dir = os.path.join('/mnt', k8s_dataset, 'catalogs') if k8s_dataset else '/tmp/ix-applications/catalogs'
        for catalog in catalogs:
            catalog.update({
                'location': os.path.join(catalogs_dir, convert_repository_to_path(catalog['repository'])),
                'id': catalog['label'],
            })
            if extra.get('item_details'):
                catalog['trains'] = await self.middleware.call(
                    'catalog.items', catalog['label'], {'cache': extra.get('cache', True)},
                )

        return filter_list(catalogs, filters, options)

    @private
    async def official_catalog_label(self):
        return OFFICIAL_LABEL
