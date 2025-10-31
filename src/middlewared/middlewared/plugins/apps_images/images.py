from middlewared.api import api_method
from middlewared.api.current import (
    AppImageEntry, AppImagePullArgs, AppImagePullResult, AppImageDeleteArgs, AppImageDeleteResult,
)
from middlewared.plugins.apps.ix_apps.docker.images import delete_image, list_images, pull_image
from middlewared.service import CRUDService, job
from middlewared.utils.filter_list import filter_list

from .utils import get_normalized_auth_config, parse_tags


class AppImageService(CRUDService):

    class Config:
        cli_namespace = 'app.image'
        namespace = 'app.image'
        role_prefix = 'APPS'
        entry = AppImageEntry

    def query(self, filters, options):
        """
        Query all docker images with `query-filters` and `query-options`.

        `query-options.extra.parse_tags` is a boolean which when set will have normalized tags to be retrieved.
        """
        if not self.middleware.call_sync('docker.state.validate', False):
            return filter_list([], filters, options)

        update_cache = self.middleware.call_sync('app.image.op.get_update_cache')
        parse_all_tags = options['extra'].get('parse_tags')
        images = []
        for image in list_images():
            config = {
                k if isinstance(k, str) else k[0]: image.get(k) if isinstance(k, str) else image.get(*k) for k in (
                    'id', ('repo_tags', []), ('repo_digests', []), 'size', 'created', 'author', 'comment',
                )
            }
            config.update({
                'dangling': len(config['repo_tags']) == 1 and config['repo_tags'][0] == '<none>:<none>',
                'update_available': any(update_cache[r] for r in config['repo_tags']),
            })
            if parse_all_tags:
                config['parsed_repo_tags'] = parse_tags(config['repo_tags'])
            images.append(config)

        return filter_list(images, filters, options)

    @api_method(AppImagePullArgs, AppImagePullResult, roles=['APPS_WRITE'])
    @job()
    def pull(self, job, data):
        """
        `image` is the name of the image to pull. Format for the name is "registry/repo/image:v1.2.3" where
        registry may be omitted and it will default to docker registry in this case. It can or cannot contain
        the tag - this will be passed as is to docker so this should be analogous to what `docker pull` expects.

        `auth_config` should be specified if image to be retrieved is under a private repository.
        """
        def callback(entry):
            nonlocal job
            # Just having some sanity checks in place in case we come across some weird registry
            if not isinstance(entry, dict) or any(
                k not in entry for k in ('progressDetail', 'status')
            ) or entry['status'].lower().strip() not in ('pull complete', 'downloading'):
                return

            if entry['status'].lower().strip() == 'pull complete':
                job.set_progress(95, 'Image downloaded, doing post processing')
                return

            progress = entry['progressDetail']
            if not isinstance(progress, dict) or any(
                k not in progress for k in ('current', 'total')
            ) or progress['current'] > progress['total']:
                return

            job.set_progress((progress['current']/progress['total']) * 90, 'Pulling image')

        self.middleware.call_sync('docker.state.validate')
        image_tag = data['image']
        auth_config = data['auth_config'] or {}
        if not auth_config:
            # If user has not provided any auth creds, we will try to see if the registry to which the image
            # belongs to, we already have it's creds and if yes we will try to use that when pulling the image
            app_registries = {
                registry['uri']: registry for registry in self.middleware.call_sync('app.registry.query')
            }
            auth_config = get_normalized_auth_config(app_registries, image_tag)

        pull_image(
            image_tag, callback, auth_config.get('username'), auth_config.get('password'),
            auth_config.get('registry_uri'),
        )
        job.set_progress(100, f'{image_tag!r} image pulled successfully')

    @api_method(AppImageDeleteArgs, AppImageDeleteResult)
    def do_delete(self, image_id, options):
        """
        Delete docker image `image_id`.

        `options.force` when set will force delete the image regardless of the state of containers and should
        be used cautiously.
        """
        self.middleware.call_sync('docker.state.validate')
        image = self.get_instance__sync(image_id)
        delete_image(image_id, options['force'])
        self.middleware.call_sync('app.image.op.remove_from_cache', image)
        return True
