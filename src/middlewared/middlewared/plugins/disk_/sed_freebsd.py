import re

from middlewared.service import Service
from middlewared.utils import run

from .sed_base import SEDBase


RE_CAMCONTROL_DRIVE_LOCKED = re.compile(r'^drive locked\s+yes$', re.M)


class DiskService(Service, SEDBase):

    async def unlock_ata_security(self, devname, _advconfig, password):
        locked = unlocked = False
        cp = await run('camcontrol', 'security', devname, check=False)
        if cp.returncode == 0:
            output = cp.stdout.decode()
            if RE_CAMCONTROL_DRIVE_LOCKED.search(output):
                locked = True
                cp = await run(
                    'camcontrol', 'security', devname, '-U', _advconfig['sed_user'], '-k', password, check=False,
                )
                if cp.returncode == 0:
                    locked = False
                    unlocked = True
            else:
                locked = False

        return locked, unlocked
