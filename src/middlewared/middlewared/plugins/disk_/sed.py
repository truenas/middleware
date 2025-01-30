import errno
import re
import subprocess

from middlewared.utils.asyncio_ import asyncio_map
from middlewared.service import CallError, Service, private
from middlewared.utils import run


RE_HDPARM_DRIVE_LOCKED = re.compile(r'Security.*\n\s*locked', re.DOTALL)
RE_SED_RDLOCK_EN = re.compile(r'(RLKEna = Y|ReadLockEnabled:\s*1)', re.M)
RE_SED_WRLOCK_EN = re.compile(r'(WLKEna = Y|WriteLockEnabled:\s*1)', re.M)


class DiskService(Service):

    @private
    async def sed_unlock_all(self, force=False):
        # on an HA system, if both controllers manage to send
        # SED commands at the same time, then it can cause issues
        # where, ultimately, the disks don't get unlocked
        if not force:  # Do not check the status if we are unlocking from vrrp_event
            if await self.middleware.call('failover.licensed'):
                if await self.middleware.call('failover.status') == 'BACKUP':
                    return

        advconfig = await self.middleware.call('system.advanced.config')
        disks = await self.middleware.call('disk.query', [], {'extra': {'passwords': True, 'real_names': True}})
        global_password = await self.middleware.call('system.advanced.sed_global_password')

        # If no SED password was found we can stop here
        if not global_password and not any([d['passwd'] for d in disks]):
            return

        result = await asyncio_map(
            lambda disk: self.sed_unlock(disk['real_name'], disk['passwd'] or global_password, advconfig, True),
            disks,
            16,
        )
        locked = list(filter(lambda x: x['locked'] is True, result))
        if locked:
            disk_names = ', '.join([i['name'] for i in locked])
            self.logger.warn(f'Failed to unlock following SED disks: {disk_names}')
            raise CallError('Failed to unlock SED disks', errno.EACCES)
        return True

    @private
    async def sed_unlock(self, disk_name, password=None, advconfig=None, force=False):
        # on an HA system, if both controllers manage to send
        # SED commands at the same time, then it can cause issues
        # where, ultimately, the disks don't get unlocked
        if not force:  # Do not check the status if we are unlocking from vrrp_event
            if await self.middleware.call('failover.licensed'):
                if await self.middleware.call('failover.status') == 'BACKUP':
                    return

        if advconfig is None:
            advconfig = await self.middleware.call('system.advanced.config')

        devname = f'/dev/{disk_name}'
        # We need two states to tell apart when disk was successfully unlocked
        locked = None
        unlocked = None
        if password is None:
            disks = await self.middleware.call(
                'disk.query',
                [['real_name', '=', disk_name]],
                {'extra': {'passwords': True, 'real_names': True}},
            )
            if disks:
                password = disks[0]['passwd']

            if password is None:
                password = await self.middleware.call('system.advanced.sed_global_password')

        rv = {'name': disk_name, 'locked': None}

        if not password:
            # If there is no password no point in continuing
            return rv

        # Try unlocking TCG OPAL using sedutil
        cp = await run('sedutil-cli', '--query', devname, check=False)
        if cp.returncode == 0:
            output = cp.stdout.decode(errors='ignore')
            if 'Locked = Y' in output:
                locked = True
                cp = await run('sedutil-cli', '--setLockingRange', '0', 'RW', password, devname, check=False)
                if cp.returncode == 0:
                    locked = False
                    unlocked = True
                    # If we were able to unlock it, let's set mbrenable to off
                    cp = await run('sedutil-cli', '--setMBREnable', 'off', password, devname, check=False)
                    if cp.returncode:
                        self.logger.error(
                            'Failed to set MBREnable for %r to "off": %s', devname,
                            cp.stderr.decode(), exc_info=True
                        )

            elif 'Locked = N' in output:
                locked = False

        # Try ATA Security if SED was not unlocked and its not locked by OPAL
        if not unlocked and not locked:
            locked, unlocked = await self.middleware.call('disk.unlock_ata_security', devname, advconfig, password)

        if locked:
            self.logger.error(f'Failed to unlock {disk_name}')

        rv['locked'] = locked
        return rv

    @private
    async def sed_initial_setup(self, disk_name, password):
        """
        NO_SED - Does not support SED
        ACCESS_GRANTED - Already setup and `password` is a valid password
        LOCKING_DISABLED - Locking range is disabled
        SETUP_FAILED - Initial setup call failed
        SUCCESS - Setup successfully completed
        """
        # on an HA system, if both controllers manage to send
        # SED commands at the same time, then it can cause issues
        # where, ultimately, the disks don't get unlocked
        if await self.middleware.call('failover.licensed'):
            if await self.middleware.call('failover.status') == 'BACKUP':
                return

        devname = f'/dev/{disk_name}'
        cp = await run('sedutil-cli', '--isValidSED', devname, check=False)
        if b' SED ' not in cp.stdout:
            return 'NO_SED'

        cp = await run('sedutil-cli', '--listLockingRange', '0', password, devname, check=False)
        if cp.returncode == 0:
            output = cp.stdout.decode()
            if RE_SED_RDLOCK_EN.search(output) and RE_SED_WRLOCK_EN.search(output):
                return 'ACCESS_GRANTED'
            else:
                return 'LOCKING_DISABLED'

        try:
            await run('sedutil-cli', '--initialSetup', password, devname)
        except subprocess.CalledProcessError as e:
            self.logger.debug(f'initialSetup failed for {disk_name}:\n{e.stdout}{e.stderr}')
            return 'SETUP_FAILED'

        # OPAL 2.0 disks do not enable locking range on setup like Enterprise does
        try:
            await run('sedutil-cli', '--enableLockingRange', '0', password, devname)
        except subprocess.CalledProcessError as e:
            self.logger.debug(f'enableLockingRange failed for {disk_name}:\n{e.stdout}{e.stderr}')
            return 'SETUP_FAILED'

        return 'SUCCESS'

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
