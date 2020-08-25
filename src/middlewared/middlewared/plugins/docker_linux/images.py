import os
import subprocess

from middlewared.service import CallError, private, CRUDService
from middlewared.utils import Popen


class DockerImagesService(CRUDService):

    class Config:
        namespace = 'docker.images'

    @private
    async def load_images_from_file(self, path):
        if not os.path.exists(path):
            raise CallError(f'"{path}" path does not exist.')

        # FIXME: Please do this in a better way
        cp = await Popen(f'docker load < {path}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        stderr = (await cp.communicate())[1]
        if cp.returncode:
            raise CallError(f'Failed to load images from file: {stderr.decode()}')
