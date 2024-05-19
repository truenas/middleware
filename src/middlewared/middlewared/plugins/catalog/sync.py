import os

from middlewared.service import private, Service

from .git_utils import pull_clone_repository


class CatalogService(Service):

    @private
    def update_git_repository(self, catalog):
        self.middleware.call_sync('network.general.will_perform_activity', 'catalog')
        return pull_clone_repository(
            catalog['repository'], os.path.dirname(catalog['location']), catalog['branch'],
        )
