import errno
import re
import subprocess

from middlewared.api import api_method
from middlewared.api.current import (
    DiskSetupSedArgs, DiskSetupSedResult, DiskUnlockSedArgs, DiskUnlockSedResult, DiskResetSedArgs, DiskResetSedResult,
)
from middlewared.service import CallError, Service, private, ValidationErrors
from middlewared.utils import run
from middlewared.utils.asyncio_ import asyncio_map
from middlewared.utils.sed import is_sed_disk, revert_sed_with_psid, SEDStatus, unlock_impl


RE_HDPARM_DRIVE_LOCKED = re.compile(r'Security.*\n\s*locked', re.DOTALL)
RE_SED_RDLOCK_EN = re.compile(r'(RLKEna = Y|ReadLockEnabled:\s*1)', re.M)
RE_SED_WRLOCK_EN = re.compile(r'(WLKEna = Y|WriteLockEnabled:\s*1)', re.M)


class DiskService(Service):

    @private
    async def setup_sed_disk_for_pool(self, disk):
        """
        Will attempt to setup SED disk for pool by either unlocking it using disk or global pass
        or alternatively set it up if it is not initialized.
        It will return true if it succeeded, false otherwise.
        """
        password = disk['passwd'] or disk['global_passwd']
        if disk['sed_status'] is SEDStatus.UNINITIALIZED:
            return await self.sed_initial_setup(disk['real_name'], password) == 'SUCCESS'
        elif disk['sed_status'] is SEDStatus.LOCKED:
            unlock_info = await unlock_impl({'path': f'/dev/{disk["real_name"]}', 'passwd': password})
            # parse unlock info returns string if it failed to unlock and none otherwise
            return await self.parse_unlock_info(unlock_info) is None

        return False

    @private
    async def setup_sed_disks_for_pool(self, disks, schema_name):
        # This will be called during pool create/update when topology is being manipulated
        # we will be doing some extra steps for SED based disks here
        # What we would like to do at this point would be to see if we have SED based disks and if yes,
        # do the following:
        # 1) We have some disks which are locked but there is no global SED pass - raise validation error
        # 2) If any of them is locked, try to unlock with global sed password
        # 3) If any of them are uninitialized, try to initialize them using global sed pass
        # 4) If anything fails in 2/3, let's raise an appropriate error
        verrors = ValidationErrors()
        sed_disks = await self.middleware.call(
            'disk.query', [['name', 'in', list(disks)], ['sed', '=', True]], {
                'extra': {'sed_status': True, 'passwords': True, 'real_names': True}, 'force_sql_filters': True
            }
        )
        to_setup_sed_disks = []
        failed_sed_status_disks = []
        for sed_disk in sed_disks:
            if sed_disk['sed_status'] in [SEDStatus.UNINITIALIZED, SEDStatus.LOCKED]:
                to_setup_sed_disks.append(sed_disk)
            elif sed_disk['sed_status'] == SEDStatus.FAILED:
                failed_sed_status_disks.append(sed_disk['name'])

        if failed_sed_status_disks:
            # Ideally shouldn't happen but if it does, let's add a validation error and raise, no point in going
            # further
            verrors.add(
                schema_name,
                f'Failed to query status of {", ".join(failed_sed_status_disks)!r} SED disk(s).'
            )
            verrors.check()

        if to_setup_sed_disks:
            global_sed_password = await self.middleware.call('system.advanced.sed_global_password')
            if not global_sed_password:
                verrors.add(
                    schema_name,
                    'Global SED password must be set when uninitialized or locked SED disks are being used in a pool'
                )
                verrors.check()

    @api_method(DiskResetSedArgs, DiskResetSedResult, roles=['DISK_WRITE'])
    async def reset_sed(self, options):
        """
        Reset SED disk.
        """
        # TODO: See if we should have validation or force flag in place to see if a disk
        #  is part of a zfs pool and to safely then allow resetting it
        disk, verrors = await self.common_sed_validation('disk_reset_sed', options)
        success, message = await revert_sed_with_psid(disk['real_name'], options['psid'])
        if not success:
            raise CallError(f'Failed to reset SED disk {disk["name"]!r} ({message})')

        # Let's please remove the password set on the disk as well at this point
        await self.middleware.call('datastore.update', 'storage_disk', disk['identifier'], {'disk_passwd': ''})
        await self.middleware.call('kmip.sync_sed_keys', [disk['identifier']])

        return True

    @private
    async def common_sed_validation(self, schema, options, status_to_check=None):
        verrors = ValidationErrors()
        if not await self.middleware.call('system.is_enterprise'):
            verrors.add(f'{schema}.name', 'This operation is only available on Enterprise systems')
        verrors.check()

        disk = await self.middleware.call('disk.query', [['name', '=', options['name']]], {
            'extra': {'sed_status': True, 'passwords': True, 'real_names': True},
            'force_sql_filters': True,
        })
        if not disk:
            verrors.add(f'{schema}.name', f'{options["name"]!r} is not a valid disk')

        verrors.check()

        disk = disk[0]
        if disk['sed'] is False:
            verrors.add(f'{schema}.name', f'{options["name"]!r} is not a SED disk')

        verrors.check()

        if status_to_check is not None and disk['sed_status'] != status_to_check:
            verrors.add(
                f'{schema}.name',
                f'{options["name"]!r} SED status is not {status_to_check} (currently is {disk['sed_status']})'
            )

        verrors.check()
        return disk, verrors

    @api_method(DiskSetupSedArgs, DiskSetupSedResult, roles=['DISK_WRITE'])
    async def setup_sed(self, options):
        """
        Setup specified `options.name` SED disk.
        """
        disk, verrors = await self.common_sed_validation('disk_sed_setup', options, SEDStatus.UNINITIALIZED)
        password = options.get('password') or disk['passwd'] or await self.middleware.call(
            'system.advanced.sed_global_password'
        )
        if not password:
            verrors.add('disk_sed_setup.password', 'Please specify a password to be used for setting up SED disk')

        verrors.check()

        status = await self.sed_initial_setup(disk['real_name'], password)
        if status != 'SUCCESS':
            raise CallError(f'Failed to set up SED disk {disk["name"]!r} (got {status!r} status)')

        # If a user had provided password, we would like to save that to the disk now
        if options.get('password'):
            await self.middleware.call('datastore.update', 'storage_disk', disk['identifier'], {
                'disk_passwd': options['password'],
            })
            await self.middleware.call('kmip.sync_sed_keys', [disk['identifier']])

        return True

    @api_method(DiskUnlockSedArgs, DiskUnlockSedResult, roles=['DISK_WRITE'])
    async def unlock_sed(self, options):
        """
        Unlock specified `options.name` SED disk.
        """
        disk, verrors = await self.common_sed_validation('disk_sed_unlock', options, SEDStatus.LOCKED)
        global_sed_password = await self.middleware.call('system.advanced.sed_global_password')
        password = options.get('password') or disk['passwd'] or global_sed_password
        if not password:
            verrors.add(
                'disk_sed_unlock.password', 'Please specify a password to be used for unlocking SED disk'
            )
        verrors.check()

        unlock_info = await unlock_impl({'path': f'/dev/{disk["real_name"]}', 'passwd': password})
        if failed_err_msg := await self.parse_unlock_info(unlock_info, True):
            raise CallError(f'Failed to unlock SED disk {disk["name"]!r} (got {failed_err_msg!r})', errno.EACCES)

        # This means that we have unlocked the SED disk
        # After discussion with William, the idea behind this method is to cater for those cases
        # where user inserted a new disk perhaps and it is locked and it's password differs from
        # the global pasword
        # In such a case, we would like to update the password in the database to reflect that case
        # but that would only be done if the password differs from the disk entry and the global sed password
        # entry
        if options.get('password'):
            # If this is set, it means that this was used to unlock the disk and it worked
            # Let's just see now that if it is same as disk pass or the global pass
            update_pass = False
            if disk['passwd']:
                if options['password'] != disk['passwd']:
                    update_pass = True
            elif global_sed_password and options['password'] != global_sed_password:
                update_pass = True

            if update_pass:
                await self.middleware.call(
                    'datastore.update',
                    'storage_disk',
                    disk['identifier'],
                    {'disk_passwd': options['password']},
                )
                await self.middleware.call('kmip.sync_sed_keys', [disk['identifier']])

        return True

    @private
    async def should_try_unlock(self, force=False):
        if force:
            # vrrp_master event will set this to True
            return True

        # on an HA system, if both controllers manage to send
        # SED commands at the same time, then it can cause issues
        # where, ultimately, the disks don't get unlocked
        return await self.middleware.call('failover.status') in ('MASTER', 'SINGLE')

    @private
    async def map_disks_to_passwd(self, disk_name=None):
        global_passwd = await self.middleware.call('system.advanced.sed_global_password')
        disks = []
        filters = [] if disk_name is None else [('real_name', '=', disk_name)]
        for disk in await self.middleware.call(
            'disk.query', filters, {'extra': {'passwords': True, 'real_names': True}}
        ):
            path = f'/dev/{disk["real_name"]}'
            # user can specify a per-disk password and/or a global password
            # we default to using the per-disk password with fallback to global
            passwd = disk['passwd'] if disk['passwd'] else global_passwd
            if passwd:
                disks.append({'path': path, 'passwd': passwd})
        return disks

    @private
    async def parse_unlock_info(self, info, return_failed_error=False):
        """Purpose of this method is to parse the unlock object
        since we have to run multiple commands for each disk.
        This will log the appropriate error message and return
        the absolute path of the disk that we failed to unlock.
        """
        if info.invalid_or_unsupported:
            # disk doesn't exist, or doesn't even return
            # properly from the --query command
            return

        errmsg = None
        failed = None
        if info.locked is True:
            failed = info.disk_path
            errmsg = f'{info.disk_path!r}'
            # means disk supports SED and we failed to unlock
            # the disk (either bad password or unhandled error)
            if info.query_cp and info.query_cp.returncode:
                errmsg += f' QUERY ERROR {info.query_cp.returncode}: {info.query_cp.stderr.decode(errors="ignore")!r}'
            if info.unlock_cp and info.unlock_cp.returncode:
                errmsg += (
                    f' UNLOCK ERROR {info.unlock_cp.returncode}: {info.unlock_cp.stderr.decode(errors="ignore")!r}'
                )
            if not return_failed_error:
                self.logger.warning(errmsg)

        if info.mbr_cp and info.mbr_cp.returncode:
            # if we successfully unlock the disk, we disable
            # the MBR shadow protection since this is a feature
            # used by the OS to protect boot partitions. We
            # dont use this functionality since we're only
            # locking/unlocking disks used in zpools.
            self.logger.warning(
                '%r MBR ERROR: %r',
                info.disk_path,
                info.mbr_cp.stderr.decode(errors="ignore")
            )

        return errmsg if return_failed_error else failed

    @private
    async def sed_unlock_all(self, force=False):
        if not await self.should_try_unlock(force):
            return

        disks_to_unlock = await self.map_disks_to_passwd()
        if not disks_to_unlock:
            # If no SED password was found for any disk
            # then there is no reason to continue
            return

        failed_to_unlock = list()
        for i in await asyncio_map(unlock_impl, disks_to_unlock, limit=16):
            if failed := await self.parse_unlock_info(i):
                failed_to_unlock.append(failed)

        if failed_to_unlock:
            raise CallError(
                'Failed to unlock SED disk(s), check /var/log/middlewared.log for details',
                errno.EACCES
            )

        return True

    @private
    async def sed_unlock_impl(self, disk_name, force=False):
        if not await self.should_try_unlock(force):
            return

        disk = await self.map_disks_to_passwd(disk_name)
        if not disk:
            return

        info = await unlock_impl(disk[0])
        failed = await self.parse_unlock_info(info)

        return failed is None or not info.locked

    @private
    async def is_sed(self, disk_name):
        return await is_sed_disk(disk_name)

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
    async def unlock_ata_security(self, devname, password):
        # FIXME: REMOVE THIS METHOD. We don't sell non-TCG password protected
        # disks so there is a high chance this does NOT work for anyone
        # with this type of drive. Unless we can test this in-house on real
        # drives, we're doing ourselves a disservice by having it. Especially
        # since this is dealing with user's data
        cp = await run('hdparm', '-I', devname, check=False)
        if cp.returncode:
            return False

        adv = await self.middleware.call('system.advanced.config')
        locked = False
        if RE_HDPARM_DRIVE_LOCKED.search(cp.stdout.decode()):
            locked = True
            cp = await run(
                [
                    'hdparm',
                    '--user-master',
                    adv['sed_user'][0].lower(),
                    '--security-unlock',
                    password,
                    devname
                ],
                check=False
            )
            if cp.returncode == 0:
                locked = False

        return locked
