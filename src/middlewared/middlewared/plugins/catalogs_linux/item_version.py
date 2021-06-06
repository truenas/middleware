import errno
import os

from middlewared.schema import accepts, Dict, Str
from middlewared.service import CallError, Service


class CatalogService(Service):

    class Config:
        cli_namespace = 'app.catalog'

    @accepts(
        Str('item_name'),
        Dict(
            'item_version_details',
            Str('catalog', required=True),
            Str('train', required=True),
        )
    )
    def get_item_details(self, item_name, options):
        """
        Retrieve information of `item_name` `item_version_details.catalog` catalog item.
        """
        catalog = self.middleware.call_sync('catalog.get_instance', options['catalog'])
        item_location = os.path.join(catalog['location'], options['train'], item_name)
        if not os.path.exists(item_location):
            raise CallError(f'Unable to locate {item_name!r} at {item_location!r}', errno=errno.ENOENT)
        return self.middleware.call_sync('catalog.retrieve_item_details', item_location)
