import re
from datetime import timedelta

from middlewared.service import job, private, Service, ServiceChangeMixin
from middlewared.utils.disks import dev_to_ident
from middlewared.utils.time_utils import utc_now


RE_IDENT = re.compile(r'^\{(?P<type>.+?)\}(?P<value>.+)$')


class DiskService(Service, ServiceChangeMixin):

    DISK_EXPIRECACHE_DAYS = 7

    @private
    async def sync(self, name: str):
        """
        Syncs a disk `name` with the database cache.
        """
        if await self.middleware.call('failover.licensed'):
            if await self.middleware.call('failover.status') == 'BACKUP':
                return

        disks = await self.middleware.call('device.get_disks')
        # Abort if the disk is not recognized as an available disk
        if name not in disks:
            return
        ident = await self.middleware.call('disk.device_to_identifier', name, disks)
        qs = await self.middleware.call(
            'datastore.query', 'storage.disk', [('disk_identifier', '=', ident)], {'order_by': ['disk_expiretime']}
        )
        if ident and qs:
            disk = qs[0]
            new = False
        else:
            new = True
            qs = await self.middleware.call('datastore.query', 'storage.disk', [('disk_name', '=', name)])
            for i in qs:
                i['disk_expiretime'] = utc_now() + timedelta(days=self.DISK_EXPIRECACHE_DAYS)
                await self.middleware.call('datastore.update', 'storage.disk', i['disk_identifier'], i)
            disk = {'disk_identifier': ident}

        disk.update({'disk_name': name, 'disk_expiretime': None})

        self._map_device_disk_to_db(disk, disks[name])

        if await self.middleware.call('system.sed_enabled') and (new or disk.get('disk_sed') is None):
            # If system is enterprise, we would like to make sure SED status is correctly reflected
            disk['disk_sed'] = await self.middleware.call('disk.is_sed', name)

        if not new:
            await self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)
        else:
            disk['disk_identifier'] = await self.middleware.call('datastore.insert', 'storage.disk', disk)

        if disks[name]['dif']:
            await self.middleware.call('alert.oneshot_create', 'DifFormatted', [name])
        else:
            await self.middleware.call('alert.oneshot_delete', 'DifFormatted', None)

        await self.restart_services_after_sync()

    @private
    def log_disk_info(self, sys_disks):
        number_of_disks = len(sys_disks)
        if number_of_disks <= 25:
            # output logging information to middlewared.log in case we sync disks
            # when not all the disks have been resolved
            log_info = {
                ok: {
                    ik: iv for ik, iv in ov.items() if ik in ('lunid', 'serial')
                } for ok, ov in sys_disks.items()
            }
            self.logger.info('Found disks: %r', log_info)
        else:
            self.logger.info('Found %d disks', number_of_disks)

        return number_of_disks

    @private
    def ident_to_dev(self, ident, sys_disks):
        if not ident or not (search := RE_IDENT.search(ident)):
            return

        tp = search.group('type')
        value = search.group('value')
        mapping = {'uuid': 'uuid', 'devicename': 'name', 'serial_lunid': 'serial_lunid', 'serial': 'serial'}
        if tp not in mapping:
            return

        for disk, info in sys_disks.items():
            if tp == 'uuid':
                for part in filter(lambda x: x['partition_uuid'] == value, info['parts']):
                    return part['disk']
            elif info.get(mapping[tp]) == value:
                return disk

    @private
    def dev_to_ident(self, name, sys_disks):
        return dev_to_ident(name, sys_disks)

    @private
    @job(lock='disk.sync_all')
    def sync_all(self, job, opts: dict[str, bool] | None = None):
        """Synchronize all disks with the cache in database."""
        # Skip sync disks on standby node
        licensed = self.middleware.call_sync('failover.licensed')
        if licensed:
            status = self.middleware.call_sync('failover.status')
            if status == 'BACKUP':
                return

        if opts is None:
            opts = dict()
        opts.setdefault('zfs_guid', False)

        job.set_progress(10, 'Enumerating system disks')
        sed_enabled_system = self.middleware.call_sync('system.sed_enabled')
        sys_disks = self.middleware.call_sync('device.get_disks', True)
        number_of_disks = self.log_disk_info(sys_disks)

        job.set_progress(20, 'Enumerating disk information from database')
        db_disks = self.middleware.call_sync('datastore.query', 'storage.disk', [], {'order_by': ['disk_expiretime']})

        options = {'send_events': False, 'ha_sync': False}
        seen_disks = {}
        added = set()
        changed = set()
        deleted = set()
        dif_formatted_disks = []
        increment = round((40 - 20) / max(number_of_disks, 1), 3)  # 20% of the total percentage
        progress_percent = 40
        for idx, disk in enumerate(db_disks, start=1):
            progress_percent += increment
            job.set_progress(progress_percent, f'Syncing disk {idx}/{number_of_disks}')

            original_disk = disk.copy()

            name = self.ident_to_dev(disk['disk_identifier'], sys_disks)
            if not name or self.dev_to_ident(name, sys_disks) != disk['disk_identifier']:
                # 1. can't translate identitifer to device
                # 2. or can't translate device to identifier
                if not disk['disk_expiretime']:
                    disk['disk_expiretime'] = utc_now() + timedelta(days=self.DISK_EXPIRECACHE_DAYS)
                    self.middleware.call_sync(
                        'datastore.update', 'storage.disk', disk['disk_identifier'], disk, options
                    )
                    deleted.add(disk['disk_identifier'])
                elif disk['disk_expiretime'] < utc_now():
                    # Disk expire time has surpassed, go ahead and remove it
                    if disk['disk_kmip_uid']:
                        self.middleware.call_sync(
                            'kmip.reset_sed_disk_password', disk['disk_identifier'], disk['disk_kmip_uuid'],
                            background=True
                        )
                    self.middleware.call_sync('datastore.delete', 'storage.disk', disk['disk_identifier'], options)
                continue
            else:
                disk['disk_expiretime'] = None
                disk['disk_name'] = name

            if name in sys_disks:
                if sys_disks[name]['dif']:
                    dif_formatted_disks.append(name)

                self._map_device_disk_to_db(disk, sys_disks[name])
                if sed_enabled_system and disk['disk_sed'] is None:
                    disk['disk_sed'] = self.middleware.call_sync('disk.is_sed', name)

            if name not in sys_disks and not disk['disk_expiretime']:
                # If for some reason disk is not identified as a system disk mark it to expire.
                disk['disk_expiretime'] = utc_now() + timedelta(days=self.DISK_EXPIRECACHE_DAYS)

            if self._disk_changed(disk, original_disk):
                self.middleware.call_sync('datastore.update', 'storage.disk', disk['disk_identifier'], disk, options)
                changed.add(disk['disk_identifier'])

            seen_disks[name] = disk

        qs = None
        progress_percent = 70
        for name in filter(lambda x: x not in seen_disks, sys_disks):
            progress_percent += increment
            disk_identifier = self.dev_to_ident(name, sys_disks)
            if qs is None:
                qs = self.middleware.call_sync('datastore.query', 'storage.disk')

            if disk := [i for i in qs if i['disk_identifier'] == disk_identifier]:
                new = False
                disk = disk[0]
                job.set_progress(progress_percent, f'Updating disk {name!r}')
            else:
                new = True
                disk = {'disk_identifier': disk_identifier}
                job.set_progress(progress_percent, f'Syncing new disk {name!r}')

            original_disk = disk.copy()
            disk['disk_name'] = name
            self._map_device_disk_to_db(disk, sys_disks[name])
            if sed_enabled_system and (new or disk.get('disk_sed') is None):
                disk['disk_sed'] = self.middleware.call_sync('disk.is_sed', name)

            if sys_disks[name]['dif']:
                dif_formatted_disks.append(name)

            if not new:
                if self._disk_changed(disk, original_disk):
                    self.middleware.call_sync(
                        'datastore.update', 'storage.disk', disk['disk_identifier'], disk, options
                    )
                    changed.add(disk['disk_identifier'])
            else:
                self.middleware.call_sync('datastore.insert', 'storage.disk', disk, options)
                added.add(disk['disk_identifier'])
                qs.append(disk)

        if dif_formatted_disks:
            self.middleware.call_sync('alert.oneshot_create', 'DifFormatted', dif_formatted_disks)
        else:
            self.middleware.call_sync('alert.oneshot_delete', 'DifFormatted', None)

        if added or changed or deleted:
            job.set_progress(92, 'Restarting necessary services')
            self.middleware.call_sync('disk.restart_services_after_sync')

            # we query the db again since we've made changes to it
            job.set_progress(94, 'Emitting disk events')
            disks = {i['identifier']: i for i in self.middleware.call_sync('disk.query')}
            for add in added:
                self.middleware.send_event('disk.query', 'ADDED', id=add, fields=disks[add])
            for change in changed:
                self.middleware.send_event('disk.query', 'CHANGED', id=change, fields=disks[change])
            for delete in deleted:
                self.middleware.send_event('disk.query', 'REMOVED', id=delete)

        if opts['zfs_guid']:
            job.set_progress(95, 'Synchronizing ZFS GUIDs')
            self.middleware.call_sync('disk.sync_all_zfs_guid')

        if licensed and status == 'MASTER':
            job.set_progress(96, 'Synchronizing database to standby controller')
            # there could be, literally, > 1k database changes in this method on large systems
            # so we're not sync'ing these db changes synchronously. Instead we're sync'ing the
            # entire database to the remote node after we're done. The (potential) speed
            # improvement this provides is substantial
            self.middleware.call_sync('failover.datastore.force_send')

        job.set_progress(100, 'Syncing all disks complete')
        return 'OK'

    def _disk_changed(self, disk, original_disk):
        # storage_disk.disk_size is a string
        return dict(disk, disk_size=None if disk.get('disk_size') is None else str(disk['disk_size'])) != original_disk

    def _map_device_disk_to_db(self, db_disk, disk):
        only_update_if_true = ('size',)
        update_keys = ('serial', 'lunid', 'rotationrate', 'type', 'size', 'subsystem', 'number', 'model', 'bus')
        for key in filter(lambda k: k in update_keys and (k not in only_update_if_true or disk[k]), disk):
            db_disk[f'disk_{key}'] = disk[key]

    @private
    def sync_size_if_changed(self, name: str):
        try:
            with open(f'/sys/block/{name}/size') as f:
                current_size = int(f.read().strip()) * 512
        except (FileNotFoundError, ValueError, OSError):
            return

        try:
            disk = self.middleware.call_sync(
                'datastore.query', 'storage.disk',
                [('disk_name', '=', name)], {'get': True}
            )
        except IndexError:
            return

        if int(disk.get('disk_size')) != current_size:
            self.middleware.call_sync(
                'datastore.update', 'storage.disk',
                disk['disk_identifier'], {'disk_size': current_size}
            )

    @private
    async def restart_services_after_sync(self):
        await self._service_change('snmp', 'restart')

    expired_disks = set()

    @private
    async def init_datastore_events_processor(self):
        self.expired_disks = {
            disk["identifier"]
            for disk in await self.middleware.call(
                "datastore.query",
                "storage.disk",
                [("expiretime", "!=", None)],
                {"prefix": "disk_"},
            )
        }

    @private
    async def process_datastore_event(self, type_, kwargs):
        if type_ == "CHANGED" and "fields" in kwargs:
            if kwargs["fields"]["expiretime"] is not None:
                if kwargs["fields"]["identifier"] not in self.expired_disks:
                    self.expired_disks.add(kwargs["fields"]["identifier"])
                    return "REMOVED", {"id": kwargs["id"]}

                return None
            else:
                if kwargs["fields"]["identifier"] in self.expired_disks:
                    self.expired_disks.remove(kwargs["fields"]["identifier"])
                    return "ADDED", {"id": kwargs["id"], "fields": kwargs["fields"]}

        return type_, kwargs


async def setup(middleware):
    await middleware.call("disk.init_datastore_events_processor")

    await middleware.call("datastore.register_event", {
        "datastore": "storage.disk",
        "plugin": "disk",
        "prefix": "disk_",
        "extra": {"include_expired": True},
        "id": "identifier",
        "process_event": "disk.process_datastore_event",
    })
