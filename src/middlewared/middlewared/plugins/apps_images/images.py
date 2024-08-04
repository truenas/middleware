from middlewared.plugins.apps.ix_apps.docker.images import list_images
from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list


class AppImageService(CRUDService):

    class Config:
        cli_namespace = 'app.image'
        namespace = 'app.image'
        role_prefix = 'APPS'

    @filterable
    def query(self, filters, options):
        """
        Query all docker images with `query-filters` and `query-options`.
        """
        if not self.middleware.call_sync('docker.state.validate', False):
            return filter_list([], filters, options)

        # id, repo_tags, repo_digests, size, dangling, created, author, comment
        images = []
        for image in list_images():
            config = {
                k if isinstance(k, str) else k[0]: image.get(k) if isinstance(k, str) else image.get(*k) for k in (
                    'id', ('repo_tags', []), ('repo_digests', []), 'size', 'created', 'author', 'comment',
                )
            }
            config['dangling'] = len(config['repo_tags']) == 1 and config['repo_tags'][0] == '<none>:<none>'
            images.append(config)

        return filter_list(images, filters, options)
