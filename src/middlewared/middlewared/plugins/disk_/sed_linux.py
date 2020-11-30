import re

from middlewared.service import Service
from middlewared.utils import run

from .sed_base import SEDBase


RE_HDPARM_DRIVE_LOCKED = re.compile(r'Security.*\n\s*locked', re.DOTALL)


class DiskService(Service, SEDBase):

    async def unlock_ata_security(self, devname, _advconfig, password):
        locked = unlocked = False
        cp = await run('hdparm', '-I', devname, check=False)
        if cp.returncode:
            return locked, unlocked

        output = cp.stdout.decode()
        if RE_HDPARM_DRIVE_LOCKED.search(output):
            locked = True
            cp = await run([
                'hdparm', '--user-master', _advconfig['sed_user'][0].lower(),
                '--security-unlock', password, devname,
            ], check=False)
            if cp.returncode == 0:
                locked = False
                unlocked = True

        return locked, unlocked
