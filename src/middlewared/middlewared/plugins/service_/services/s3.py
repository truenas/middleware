from .base import SimpleService


class S3Service(SimpleService):
    name = "s3"

    etc = ["s3"]

    freebsd_rc = "minio"
    freebsd_pidfile = "/var/run/minio.pid"
