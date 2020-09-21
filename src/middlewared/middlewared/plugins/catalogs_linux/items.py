import os

from middlewared.service import accepts, CallError, Service


class CatalogService(Service):

    @accepts()
    def catalog_items(self, label):
        catalog = self.middleware.call_sync('catalog.get_instance', label)
        if not os.path.exists(catalog['location']):
            raise CallError(f'Catalog location {catalog["location"]} does not exist.')
