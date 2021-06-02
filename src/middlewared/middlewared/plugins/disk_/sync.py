import asyncio

from datetime import datetime, timedelta

from middlewared.schema import accepts, Str
from middlewared.service import job, private, Service, ServiceChangeMixin


class DiskService(Service, ServiceChangeMixin):

    DISK_EXPIRECACHE_DAYS = 7

    @private
    @accepts(Str('name'))
    async def sync(self, name):
        """
        Syncs a disk `name` with the database cache.
        """
        if await self.middleware.call('failover.licensed'):
            if await self.middleware.call('failover.status') == 'BACKUP':
                return

        # Do not sync geom classes like multipath/hast/etc
        if name.find('/') != -1:
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
                i['disk_expiretime'] = datetime.utcnow() + timedelta(days=self.DISK_EXPIRECACHE_DAYS)
                await self.middleware.call('datastore.update', 'storage.disk', i['disk_identifier'], i)
            disk = {'disk_identifier': ident}

        disk.update({'disk_name': name, 'disk_expiretime': None})

        await self._map_device_disk_to_db(disk, disks[name])

        if not new:
            await self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)
        else:
            disk['disk_identifier'] = await self.middleware.call('datastore.insert', 'storage.disk', disk)

        await self.restart_services_after_sync()

        await self.middleware.call('enclosure.sync_disk', disk['disk_identifier'])

    @private
    @accepts()
    @job(lock='disk.sync_all')
    async def sync_all(self, job):
        """
        Synchronize all disks with the cache in database.
        """
        # Skip sync disks on standby node
        if await self.middleware.call('failover.licensed'):
            if await self.middleware.call('failover.status') == 'BACKUP':
                return

        sys_disks = await self.middleware.call('device.get_disks')

        # output logging information to middlewared.log in case we sync disks
        # when not all the disks have been resolved
        log_info = {
            ok: {
                ik: iv for ik, iv in ov.items() if ik in ('name', 'ident', 'lunid', 'serial')
            } for ok, ov in sys_disks.items()
        }
        self.logger.info('Found disks: %r', log_info)

        seen_disks = {}
        serials = []
        changed = False
        for disk in (
            await self.middleware.call('datastore.query', 'storage.disk', [], {'order_by': ['disk_expiretime']})
        ):
            original_disk = disk.copy()

            name = await self.middleware.call('disk.identifier_to_device', disk['disk_identifier'], sys_disks)
            if (
                    not name or
                    name in seen_disks or
                    await self.middleware.call('disk.device_to_identifier', name) != disk['disk_identifier']
            ):
                # If we cant translate the identifier to a device, give up
                # If name has already been seen once then we are probably
                # dealing with with multipath here
                if not disk['disk_expiretime']:
                    disk['disk_expiretime'] = datetime.utcnow() + timedelta(days=self.DISK_EXPIRECACHE_DAYS)
                    await self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)
                    changed = True
                elif disk['disk_expiretime'] < datetime.utcnow():
                    # Disk expire time has surpassed, go ahead and remove it
                    if disk['disk_kmip_uid']:
                        asyncio.ensure_future(self.middleware.call(
                            'kmip.reset_sed_disk_password', disk['disk_identifier'], disk['disk_kmip_uid']
                        ))
                    await self.middleware.call('datastore.delete', 'storage.disk', disk['disk_identifier'])
                    changed = True
                continue
            else:
                disk['disk_expiretime'] = None
                disk['disk_name'] = name

            if name in sys_disks:
                await self._map_device_disk_to_db(disk, sys_disks[name])

            serial = (disk['disk_serial'] or '') + (sys_disks.get(name, {}).get('lunid') or '')
            if serial:
                serials.append(serial)

            # If for some reason disk is not identified as a system disk
            # mark it to expire.
            if name not in sys_disks and not disk['disk_expiretime']:
                disk['disk_expiretime'] = datetime.utcnow() + timedelta(days=self.DISK_EXPIRECACHE_DAYS)
            # Do not issue unnecessary updates, they are slow on HA systems and cause severe boot delays
            # when lots of drives are present
            if self._disk_changed(disk, original_disk):
                await self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)
                changed = True

            try:
                await self.middleware.call('enclosure.sync_disk', disk['disk_identifier'])
            except Exception:
                self.middleware.logger.error('Unhandled exception in enclosure.sync_disk for %r',
                                             disk['disk_identifier'], exc_info=True)

            seen_disks[name] = disk

        for name in sys_disks:
            if name not in seen_disks:
                disk_identifier = await self.middleware.call('disk.device_to_identifier', name, sys_disks)
                qs = await self.middleware.call(
                    'datastore.query', 'storage.disk', [('disk_identifier', '=', disk_identifier)]
                )
                if qs:
                    new = False
                    disk = qs[0]
                else:
                    new = True
                    disk = {'disk_identifier': disk_identifier}
                original_disk = disk.copy()
                disk['disk_name'] = name
                await self._map_device_disk_to_db(disk, sys_disks[name])
                serial = disk['disk_serial'] + (sys_disks[name]['lunid'] or '')
                if serial:
                    if serial in serials:
                        # Probably dealing with multipath here, do not add another
                        continue
                    else:
                        serials.append(serial)

                if not new:
                    # Do not issue unnecessary updates, they are slow on HA systems and cause severe boot delays
                    # when lots of drives are present
                    if self._disk_changed(disk, original_disk):
                        await self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)
                        changed = True
                else:
                    await self.middleware.call('datastore.insert', 'storage.disk', disk)
                    changed = True

                try:
                    await self.middleware.call('enclosure.sync_disk', disk['disk_identifier'])
                except Exception:
                    self.middleware.logger.error('Unhandled exception in enclosure.sync_disk for %r',
                                                 disk['disk_identifier'], exc_info=True)

        if changed:
            await self.middleware.call('disk.restart_services_after_sync')
        return 'OK'

    def _disk_changed(self, disk, original_disk):
        # storage_disk.disk_size is a string
        return dict(disk, disk_size=None if disk.get('disk_size') is None else str(disk['disk_size'])) != original_disk

    async def _map_device_disk_to_db(self, db_disk, disk):
        only_update_if_true = ('size',)
        update_keys = ('serial', 'rotationrate', 'type', 'size', 'subsystem', 'number', 'model')
        for key in filter(lambda k: k in update_keys and (k not in only_update_if_true or disk[k]), disk):
            db_disk[f'disk_{key}'] = disk[key]

    @private
    async def restart_services_after_sync(self):
        await self.middleware.call('disk.update_hddstandby_force')
        await self.middleware.call('disk.update_smartctl_args_for_disks')
        if await self.middleware.call('service.started', 'collectd'):
            await self.middleware.call('service.restart', 'collectd')
        await self._service_change('smartd', 'restart')
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
    async def process_datastore_event(self, type, kwargs):
        if type == "CHANGED" and "fields" in kwargs:
            if kwargs["fields"]["expiretime"] is not None:
                if kwargs["fields"]["identifier"] not in self.expired_disks:
                    self.expired_disks.add(kwargs["fields"]["identifier"])
                    return "CHANGED", {"id": kwargs["id"], "cleared": True}

                return None
            else:
                if kwargs["fields"]["identifier"] in self.expired_disks:
                    self.expired_disks.remove(kwargs["fields"]["identifier"])
                    return "ADDED", {"id": kwargs["id"], "fields": kwargs["fields"]}

        return type, kwargs


async def setup(middleware):
    await middleware.call("disk.init_datastore_events_processor")

    await middleware.call("datastore.register_event", {
        "description": "Sent on disk changes.",
        "datastore": "storage.disk",
        "plugin": "disk",
        "prefix": "disk_",
        "extra": {"include_expired": True},
        "id": "identifier",
        "process_event": "disk.process_datastore_event",
    })
