import subprocess

from middlewared.service import private, Service


class FencedForceService(Service):

    class Config:
        namespace = 'failover.fenced'

    @private
    def force(self):

        cp = subprocess.run(
            ['fenced', '--force'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        if cp.returncode not in (0, 6):
            return False

        return True
