import subprocess

from middlewared.service import Service


class FencedForceService(Service):

    class Config:
        private = True
        namespace = 'failover.fenced'

    def force(self):

        # fenced will reserve nvme drives so we need to make sure
        # that the boot disks (newer generation m-series use nvme boot drives)
        # are excluded (-ed flag) from fenced so SCSI reservations are not
        # placed on them
        boot_disks = ",".join(self.middleware.call_sync('boot.get_disks'))

        cp = subprocess.run(
            ['fenced', '--force', '-ed', f'{boot_disks}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        if cp.returncode not in (0, 6):
            return False

        return True
