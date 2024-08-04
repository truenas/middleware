from middlewared.plugins.apps.ix_apps.docker.images import list_images
from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list


class AppImageService(CRUDService):

    class Config:
        namespace = 'app.image'
        role_prefix = 'APPS'

    @filterable
    def query(self, filters, options):
        """
        Query all docker images with `query-filters` and `query-options`.
        """
        if not self.middleware.call_sync('docker.state.validate', False):
            return filter_list([], filters, options)

        return []
