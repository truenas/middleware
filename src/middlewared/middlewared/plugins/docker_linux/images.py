import aiodocker
import errno
import os

from datetime import datetime

from middlewared.service import CallError, filterable, private, CRUDService
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

    @private
    async def load_images_from_file(self, path):
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
