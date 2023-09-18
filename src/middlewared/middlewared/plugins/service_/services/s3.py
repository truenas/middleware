from middlewared.service import CallError

from .base import SimpleService


class S3Service(SimpleService):
    name = "s3"
    deprecated = True

    etc = ["s3"]

    freebsd_rc = "minio"
    freebsd_pidfile = "/var/run/minio.pid"

    systemd_unit = "minio"

    async def start(self):
        raise CallError('S3 service is deprecated')
