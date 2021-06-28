import aiodocker
import errno
import itertools
import os

from copy import deepcopy
from datetime import datetime

from middlewared.schema import Bool, Datetime, Dict, Int, List, returns, Str
from middlewared.service import accepts, CallError, filterable, job, private, CRUDService
from middlewared.utils import filter_list

from .utils import DEFAULT_DOCKER_IMAGES_LIST_PATH, DEFAULT_DOCKER_REGISTRY, DEFAULT_DOCKER_REPO


DEFAULT_DOCKER_IMAGES_PATH = '/usr/local/share/docker_images/docker-images.tar'


class DockerImagesService(CRUDService):

    class Config:
        datastore_primary_key_type = 'string'
        namespace = 'container.image'
        namespace_alias = 'docker.images'
        cli_namespace = 'app.docker.image'

    ENTRY = Dict(
        'container_image_entry',
        Str('id'),
        Dict('labels', additional_attrs=True),
        List('repo_tags', items=[Str('repo_tag')]),
        List('repo_digests', items=[Str('repo_digest')]),
        Int('size'),
        Bool('dangling'),
        Bool('update_available'),
        Bool('system_image'),
        Datetime('created'),
        List('parsed_repo_tags', items=[Dict(
            'parsed_repo_tag',
            Str('image'),
            Str('tag'),
            Str('registry'),
            Str('complete_tag'),
        )])
    )

    @filterable
    async def query(self, filters, options):
        """
        Retrieve container images present in the system.

        `query-options.extra.parse_tags` is a boolean which when set will have normalized tags to be retrieved
        for container images.
        """
        results = []
        if not await self.middleware.call('service.started', 'docker'):
            return results

        extra = deepcopy(options.get('extra', {}))
        update_cache = await self.middleware.call('container.image.image_update_cache')
        system_images = await self.middleware.call('container.image.get_system_images_tags')
        parse_tags = extra.get('parse_tags', False)

        async with aiodocker.Docker() as docker:
            for image in await docker.images.list():
                repo_tags = image['RepoTags'] or []
                system_image = any(tag in system_images for tag in repo_tags)
                results.append({
                    'id': image['Id'],
                    'labels': image['Labels'] or {},
                    'repo_tags': repo_tags,
                    'repo_digests': image.get('RepoDigests') or [],
                    'size': image['Size'],
                    'created': datetime.fromtimestamp(int(image['Created'])),
                    'dangling': len(repo_tags) == 1 and repo_tags[0] == '<none>:<none>',
                    'update_available': not system_image and any(update_cache[r] for r in repo_tags),
                    'system_image': system_image,
                    **(
                        {'parsed_repo_tags': await self.middleware.call('container.image.parse_tags', repo_tags)}
                        if parse_tags else {}
                    )
                })
        return filter_list(results, filters, options)

    @accepts(
        Dict(
            'image_pull',
            Dict(
                'docker_authentication',
                Str('username', required=True),
                Str('password', required=True),
                default=None,
                null=True,
            ),
            Str('from_image', required=True),
            Str('tag', default=None, null=True),
        )
    )
    @returns(List(items=[Dict('pull_result_entry', Str('status'), additional_attrs=True)]))
    @job()
    async def pull(self, job, data):
        """
        `from_image` is the name of the image to pull. Format for the name is "registry/repo/image" where
        registry may be omitted and it will default to docker registry in this case.

        `tag` specifies tag of the image and defaults to `null`. In case of `null` it will retrieve all the tags
        of the image.

        `docker_authentication` should be specified if image to be retrieved is under a private repository.
        """
        await self.docker_checks()
        # TODO: Have job progress report downloading progress
        async with aiodocker.Docker() as docker:
            try:
                response = await docker.images.pull(
                    from_image=data['from_image'], tag=data['tag'], auth=data['docker_authentication']
                )
            except aiodocker.DockerError as e:
                raise CallError(f'Failed to pull image: {e.message}')

        await self.middleware.call('container.image.clear_update_flag_for_tag', f'{data["from_image"]}:{data["tag"]}')

        return response

    @accepts(
        Str('id'),
        Dict(
            'options',
            Bool('force', default=False),
        )
    )
    @returns()
    async def do_delete(self, id, options):
        """
        `options.force` should be used to force delete an image even if it's in use by a stopped container.
        """
        await self.docker_checks()
        image = await self.get_instance(id)
        if image['system_image']:
            raise CallError(f'{id} is being used by system and cannot be deleted.')

        async with aiodocker.Docker() as docker:
            await docker.images.delete(name=id, force=options['force'])

        await self.middleware.call('container.image.remove_image_from_cache', image)

    @private
    async def load_images_from_file(self, path):
        await self.docker_checks()
        if not os.path.exists(path):
            raise CallError(f'"{path}" path does not exist.', errno=errno.ENOENT)

        resp = []
        async with aiodocker.Docker() as client:
            with open(path, 'rb') as f:
                async for i in client.images.import_image(data=f, stream=True):
                    if 'error' in i:
                        raise CallError(f'Unable to load images from file: {i["error"]}')
                    else:
                        resp.append(i)
        return resp

    @private
    async def load_default_images(self):
        await self.load_images_from_file(DEFAULT_DOCKER_IMAGES_PATH)

    @private
    async def docker_checks(self):
        if not await self.middleware.call('service.started', 'docker'):
            raise CallError('Docker service is not running')

    @private
    def normalise_tag(self, tag):
        tags = [tag]
        i = tag.find('/')
        if i == -1 or (not any(c in tag[:i] for c in ('.', ':')) and tag[:i] != 'localhost'):
            for registry in (DEFAULT_DOCKER_REGISTRY, 'docker.io'):
                tags.append(f'{registry}/{tag}')
                if '/' not in tag:
                    tags.append(f'{registry}/{DEFAULT_DOCKER_REPO}/{tag}')
        else:
            if tag.startswith('docker.io/'):
                tags.append(f'{DEFAULT_DOCKER_REGISTRY}/{tag[len("docker.io/"):]}')
            elif tag.startswith(DEFAULT_DOCKER_REGISTRY):
                tags.append(f'docker.io/{tag[len(DEFAULT_DOCKER_REGISTRY):]}')
        return tags

    @private
    def get_system_images_tags(self):
        with open(DEFAULT_DOCKER_IMAGES_LIST_PATH, 'r') as f:
            images = [i for i in map(str.strip, f.readlines()) if i]

        images.extend([
            'nvidia/k8s-device-plugin:1.0.0-beta6',
            'k8s.gcr.io/sig-storage/csi-node-driver-registrar:v2.1.0',
            'k8s.gcr.io/sig-storage/csi-provisioner:v2.1.0',
            'k8s.gcr.io/sig-storage/csi-resizer:v1.1.0',
            'k8s.gcr.io/sig-storage/snapshot-controller:v4.0.0',
            'k8s.gcr.io/sig-storage/csi-snapshotter:v4.0.0',
            'openebs/zfs-driver:ci',
        ])
        return list(itertools.chain(
            *[self.normalise_tag(tag) for tag in images]
        ))
