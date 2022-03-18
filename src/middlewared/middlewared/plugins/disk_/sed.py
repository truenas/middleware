import re

from middlewared.service import Service, private
from middlewared.utils import run


RE_HDPARM_DRIVE_LOCKED = re.compile(r'Security.*\n\s*locked', re.DOTALL)


class DiskService(Service):

    @private
    async def unlock_ata_security(self, devname, _adv, password):
        locked = unlocked = False
        cp = await run('hdparm', '-I', devname, check=False)
        if cp.returncode:
            return locked, unlocked

        output = cp.stdout.decode()
        if RE_HDPARM_DRIVE_LOCKED.search(output):
            locked = True
            cmd = ['hdparm', '--user-master', _adv['sed_user'][0].lower(), '--security-unlock', password, devname]
            cp = await run(cmd, check=False)
            if cp.returncode == 0:
                locked = False
                unlocked = True

        return locked, unlocked
