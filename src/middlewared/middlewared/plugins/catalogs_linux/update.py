from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list


CATALOGS = [
    {
        'label': 'OFFICIAL',
        'repository': 'https://github.com/sonicaj/charts.git',
    }
]


class CatalogService(CRUDService):

    @filterable
    async def query(self, filters=None, options=None):
        return filter_list(CATALOGS, filters, options)
