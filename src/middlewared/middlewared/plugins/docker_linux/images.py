import aiodocker
import errno
import os

from datetime import datetime

from middlewared.schema import Bool, Dict, Str
from middlewared.service import accepts, CallError, filterable, private, CRUDService
from middlewared.utils import filter_list


DEFAULT_DOCKER_IMAGES_PATH = '/usr/local/share/docker_images/docker-images.tar'


class DockerImagesService(CRUDService):

    class Config:
        namespace = 'docker.images'

    @filterable
    async def query(self, filters=None, options=None):
        results = []
        if not await self.middleware.call('service.started', 'docker'):
            return results

        async with aiodocker.Docker() as docker:
            for image in await docker.images.list():
                repo_tags = image['RepoTags'] or []
                results.append({
                    'id': image['Id'],
                    'labels': image['Labels'],
                    'repo_tags': repo_tags,
                    'size': image['Size'],
                    'created': datetime.fromtimestamp(int(image['Created'])),
                    'dangling': len(repo_tags) == 1 and repo_tags[0] == '<none>:<none>',
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
    async def pull(self, data):
        """
        `from_image` is the name of the image to pull. Format for the name is "registry/repo/image" where
        registry may be omitted and it will default to docker registry in this case.

        `tag` specifies tag of the image and defaults to `null`. In case of `null` it will retrieve all the tags
        of the image.

        `docker_authentication` should be specified if image to be retrieved is under a private repository.
        """
        await self.docker_checks()
        async with aiodocker.Docker() as docker:
            try:
                response = await docker.images.pull(
                    from_image=data['from_image'], tag=data['tag'], auth=data['docker_authentication']
                )
            except aiodocker.DockerError as e:
                raise CallError(f'Failed to pull image: {e.message}')
        return response

    @accepts(
        Str('id'),
        Dict(
            'options',
            Bool('force', default=False),
        )
    )
    async def do_delete(self, id, options):
        """
        `options.force` should be used to force delete an image even if it's in use by a stopped container.
        """
        await self.docker_checks()
        async with aiodocker.Docker() as docker:
            await docker.images.delete(name=id, force=options['force'])

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
