import aiodocker
import os

from middlewared.service import CallError, private, CRUDService


DEFAULT_DOCKER_IMAGES_PATH = '/usr/local/share/docker_images/docker-images.tar'


class DockerImagesService(CRUDService):

    class Config:
        namespace = 'docker.images'

    @private
    async def load_images_from_file(self, path):
        if not os.path.exists(path):
            raise CallError(f'"{path}" path does not exist.')

        client = aiodocker.Docker()
        resp = []
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
