import asyncio
import errno

from middlewared.api import api_method
from middlewared.api.current import (
    DiskSetupSedArgs, DiskSetupSedResult, DiskUnlockSedArgs, DiskUnlockSedResult, DiskResetSedArgs, DiskResetSedResult,
)
from middlewared.service import CallError, Service, private, ValidationErrors
from middlewared.utils.asyncio_ import asyncio_map
from middlewared.utils.disks_.disk_class import DiskEntry


class DiskService(Service):

    @private
    async def setup_sed_disk(self, disk):
        """
        Will attempt to setup SED disk for pool by either unlocking it using disk or global pass
        or alternatively set it up if it is not initialized.
        It will return tuple true if it succeeded, false otherwise with the other value being disk name
        """
        password = disk['passwd'] or disk['global_passwd']
        entry = DiskEntry(name=disk['real_name'], devpath=f'/dev/{disk["real_name"]}')
        if disk['sed_status'] == 'UNINITIALIZED':
            result = await asyncio.to_thread(entry.sed_initial_setup, password)
            return result == 'SUCCESS', disk['name']
        elif disk['sed_status'] == 'LOCKED':
            success, error = await asyncio.to_thread(entry.sed_unlock, password)
            return success, disk['name']

        return False, disk['name']

    @private
    async def setup_sed_disks_for_pool(self, disks, schema_name, validate_all_disks_are_sed=False):
        # This will be called during pool create/update when topology is being manipulated
        # we will be doing some extra steps for SED based disks here
        # What we would like to do at this point would be to see if we have SED based disks and if yes,
        # do the following:
        # 1) We have some disks which are locked but there is no global SED pass - raise validation error
        # 2) If any of them is locked, try to unlock with global sed password
        # 3) If any of them are uninitialized, try to initialize them using global sed pass
        # 4) If anything fails in 2/3, let's raise an appropriate error
        verrors = ValidationErrors()
        filters = [['name', 'in', list(disks)]]
        if validate_all_disks_are_sed is False:
            filters.append(['sed', '=', True])

        disks_to_check = await self.middleware.call(
            'disk.query', filters, {
                'extra': {'sed_status': True, 'passwords': True, 'real_names': True}, 'force_sql_filters': True
            }
        )
        to_setup_sed_disks = []
        failed_sed_status_disks = []
        non_sed_disks = []
        for disk in disks_to_check:
            if validate_all_disks_are_sed and disk['sed'] is False:
                non_sed_disks.append(disk['name'])
            if disk['sed_status'] in ['UNINITIALIZED', 'LOCKED']:
                to_setup_sed_disks.append(disk)
            elif disk['sed_status'] == 'FAILED':
                failed_sed_status_disks.append(disk['name'])

        if non_sed_disks:
            verrors.add(
                schema_name,
                f'Following disk(s) are not SED: {", ".join(non_sed_disks)!r}',
            )

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

            failed_setup_disks = []
            for success, disk_name in await asyncio_map(
                self.setup_sed_disk, [d | {'global_passwd': global_sed_password} for d in to_setup_sed_disks],
                limit=16
            ):
                if success is False:
                    failed_setup_disks.append(disk_name)

            if failed_setup_disks:
                verrors.add(
                    schema_name,
                    f'Failed to setup {", ".join(failed_setup_disks)!r} SED disk(s).'
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
        entry = DiskEntry(name=disk['real_name'], devpath=f'/dev/{disk["real_name"]}')
        success, message = await asyncio.to_thread(entry.sed_factory_reset, options['psid'])
        if not success:
            raise CallError(f'Failed to reset SED disk {disk["name"]!r} ({message})')

        # Let's please remove the password set on the disk as well at this point
        await self.middleware.call('datastore.update', 'storage_disk', disk['identifier'], {'disk_passwd': ''})
        await self.middleware.call('kmip.sync_sed_keys', [disk['identifier']])

        return True

    @private
    async def common_sed_validation(self, schema, options, status_to_check=None):
        verrors = ValidationErrors()
        if not await self.middleware.call('system.sed_enabled'):
            verrors.add(f'{schema}.name', 'System is not licensed for SED functionality.')
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
                f'{options["name"]!r} SED status is not {status_to_check} (currently is {disk["sed_status"]})'
            )

        verrors.check()
        return disk, verrors

    @api_method(DiskSetupSedArgs, DiskSetupSedResult, roles=['DISK_WRITE'])
    async def setup_sed(self, options):
        """
        Setup specified `options.name` SED disk.
        """
        disk, verrors = await self.common_sed_validation('disk_sed_setup', options, 'UNINITIALIZED')
        password = options.get('password') or disk['passwd'] or await self.middleware.call(
            'system.advanced.sed_global_password'
        )
        if not password:
            verrors.add('disk_sed_setup.password', 'Please specify a password to be used for setting up SED disk')

        verrors.check()

        entry = DiskEntry(name=disk['real_name'], devpath=f'/dev/{disk["real_name"]}')
        status = await asyncio.to_thread(entry.sed_initial_setup, password)
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
        disk, verrors = await self.common_sed_validation('disk_sed_unlock', options, 'LOCKED')
        global_sed_password = await self.middleware.call('system.advanced.sed_global_password')
        password = options.get('password') or disk['passwd'] or global_sed_password
        if not password:
            verrors.add(
                'disk_sed_unlock.password', 'Please specify a password to be used for unlocking SED disk'
            )
        verrors.check()

        entry = DiskEntry(name=disk['real_name'], devpath=f'/dev/{disk["real_name"]}')
        success, error = await asyncio.to_thread(entry.sed_unlock, password)
        if not success:
            raise CallError(f'Failed to unlock SED disk {disk["name"]!r} ({error!r})', errno.EACCES)

        # After discussion with William, the idea behind this method is to cater for those cases
        # where user inserted a new disk perhaps and it is locked and it's password differs from
        # the global password.
        # In such a case, we would like to update the password in the database to reflect that case
        # but that would only be done if the password differs from the disk entry and the global sed password
        # entry.
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
            name = disk['real_name']
            # user can specify a per-disk password and/or a global password
            # we default to using the per-disk password with fallback to global
            passwd = disk['passwd'] if disk['passwd'] else global_passwd
            if passwd:
                disks.append({'name': name, 'passwd': passwd})
        return disks

    @private
    async def sed_unlock_all(self, force=False):
        if not await self.should_try_unlock(force):
            return

        disks_to_unlock = await self.map_disks_to_passwd()
        if not disks_to_unlock:
            return

        def _unlock(d):
            entry = DiskEntry(name=d['name'], devpath=f'/dev/{d["name"]}')
            return d['name'], *entry.sed_unlock(d['passwd'])

        failed_to_unlock = []
        for name, success, error in await asyncio_map(_unlock, disks_to_unlock, limit=16):
            if not success:
                self.logger.warning('/dev/%s: failed to unlock SED disk: %s', name, error)
                failed_to_unlock.append(name)

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

        d = disk[0]
        entry = DiskEntry(name=d['name'], devpath=f'/dev/{d["name"]}')
        success, error = await asyncio.to_thread(entry.sed_unlock, d['passwd'])
        return success

    @private
    def is_sed(self, disk_name):
        return DiskEntry(name=disk_name, devpath=f'/dev/{disk_name}').is_sed()

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

        entry = DiskEntry(name=disk_name, devpath=f'/dev/{disk_name}')
        return await asyncio.to_thread(entry.sed_initial_setup, password)
