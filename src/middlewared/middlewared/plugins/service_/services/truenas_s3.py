from .base import SimpleService


class TrueNASS3Service(SimpleService):
    name = "truenas_s3"
    etc = ["truenas_s3"]
    reloadable = True
    restartable = True
    may_run_on_standby = False
    systemd_unit = "truenas_s3"
