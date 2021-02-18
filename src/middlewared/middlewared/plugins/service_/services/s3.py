from middlewared.service import CallError

from .base import SimpleService


class S3Service(SimpleService):
    name = "s3"

    etc = ["s3"]

    freebsd_rc = "minio"
    freebsd_pidfile = "/var/run/minio.pid"

    systemd_unit = "minio"

    async def before_start(self):
        storage_path = (await self.middleware.call('s3.config'))['storage_path']
        if not storage_path:
            raise CallError('Storage path must be set to start S3 service')
        if await self.middleware.call('pool.dataset.path_in_locked_datasets', storage_path):
            raise CallError('Unable to start S3 service as storage path is accessing a locked dataset')
