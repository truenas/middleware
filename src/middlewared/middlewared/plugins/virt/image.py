import usb.core

from middlewared.service import CallError, Service, job

from middlewared.api import api_method
from middlewared.api.current import (
    VirtImageUploadArgs, VirtImageUploadResult,
)

from .utils import incus_call_and_wait


class VirtImageService(Service):

    class Config:
        namespace = 'virt.image'
        cli_namespace = 'virt.image'

    @api_method(VirtImageUploadArgs, VirtImageUploadResult, roles=['VIRT_IMAGE_WRITE'])
    @job(pipes=["input"])
    async def import_file(self, job):
        """
        Import provided instance image.
        """
        # FIXME: waiting support for multiple files upload in middleware
        with open('/mnt/tank/meta-d783ab3f9c02b78449693ac6a479c40891152d521a26be6a95003fcd83a77046.tar.xz', 'rb') as foo:
            result = await incus_call_and_wait('1.0/images', 'post', {
                'data': {
                    'metadata': foo,
                    'rootfs': job.pipes.input.r,
                },
            })
        result['size'] = int(result['size'])
        return result

