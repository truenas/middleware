import subprocess

from middlewared.service import private, Service


class InternalInterfaceDetectionService(Service):

    class Config:
        namespace = 'failover.internal_interface'

    @private
    def detect(self):

        hardware = self.middleware.call_sync(
            'failover.hardware'
        )

        if hardware == 'ECHOSTREAM':
            proc = subprocess.check_output(
                '/usr/sbin/pciconf -lv | grep "device=0x10d3 subvendor=0x8086 subdevice=0xa01f"',
                shell=True,
                encoding='utf8',
            )
            if proc:
                return [proc.split('@')[0]]

        if hardware in ('ECHOWARP', 'PUMA'):
            return ['ntb0']

        if hardware == 'BHYVE':
            return ['vtnet1']

        if hardware == 'SBB':
            return ['ix0']

        if hardware == 'ULTIMATE':
            return ['igb1']

        return []
