from middlewared.schema import accepts
from middlewared.service import Service


class WebUIEnclosureService(Service):
    class Config:
        namespace = 'webui.enclosure'
        private = True
        cli_private = True
        role_prefix = 'ENCLOSURE'

    def disk_detail_dict(self):
        return {
            'size': None,
            'model': None,
            'serial': None,
            'type': None,
            'rotationrate': None,
        }

    def map_disk_details(self, slot_info, disk_deets):
        for key in self.disk_detail_dict():
            slot_info[key] = disk_deets.get(slot_info['dev'], {}).get(key)

    def map_zpool_info(self, enc_id, disk_slot, dev, pool_info):
        info = {'enclosure_id': enc_id, 'slot': int(disk_slot), 'dev': dev}
        try:
            index = pool_info['vdev_disks'].index(dev)
            pool_info['vdev_disks'][index] = info
        except ValueError:
            # it means the disk's status in zfs land != ONLINE
            # (i.e. it could be OFFLINE) and so it won't show
            # up in the `vdev_disks` key, so it's best to catch
            # this error and still append the disk to the list
            # The `pool_info['disk_status']` key will be added
            # which will give more insight into what's going on
            pool_info['vdev_disks'].append(info)

    def dashboard_impl(self):
        enclosures = self.middleware.call_sync('enclosure2.query')
        if enclosures:
            disk_deets = self.middleware.call_sync('device.get_disks')
            disks_to_pools = self.middleware.call_sync('zpool.status', {'real_paths': True})
            for enc in enclosures:
                for disk_slot, slot_info in enc['elements']['Array Device Slot'].items():
                    for to_pop in ('original', 'value', 'value_raw'):
                        # remove some values that webUI doesn't use
                        slot_info.pop(to_pop)

                    pool_info = None
                    slot_info.update({'drive_bay_number': int(disk_slot), **self.disk_detail_dict()})
                    if slot_info['dev']:
                        # map disk details
                        # NOTE: some of these fields need to be removed
                        # work with UI to remove unnecessary ones
                        self.map_disk_details(slot_info, disk_deets)

                        if pool_info := disks_to_pools['disks'].get(slot_info['dev']):
                            # now map zpool info
                            self.map_zpool_info(enc['id'], disk_slot, slot_info['dev'], pool_info)

                    slot_info.update({'pool_info': pool_info})

        return enclosures

    @accepts(roles=['ENCLOSURE_READ'])
    def dashboard(self):
        """This endpoint is used exclusively by the webUI team for
        the enclosure dashboard page for iX sold hardware.

        An example of what this returns looks like the following:
            (NOTE: some redundant information cut out for brevity)
        [{
            "name": "iX 4024Sp c205",
            "model": "M40",
            "controller": true,
            "dmi": "TRUENAS-M40-HA",
            "status": ["OK"],
            "id": "5b0bd6d1a30714bf",
            "vendor": "iX",
            "product": "4024Sp",
            "revision": "c205",
            "bsg": "/dev/bsg/0:0:23:0",
            "sg": "/dev/sg25",
            "pci": "0:0:23:0",
            "rackmount": true,
            "top_loaded": false,
            "front_slots": 24,
            "rear_slots": 0,
            "internal_slots": 0,
            "elements": {
                "Array Device Slot": {
                    "1": {
                        "descriptor": "slot00",
                        "status": "OK",
                        "dev": "sda",
                        "supports_identify_light": true,
                        "name": "sda",
                        "size": 12000138625024,
                        "model": "HUH721212AL4200",
                        "serial": "XXXXX",
                        "advpowermgmt": "DISABLED",
                        "togglesmart": true,
                        "smartoptions": "",
                        "transfermode": "Auto",
                        "hddstandby": "ALWAYS ON",
                        "description": "",
                        "rotationrate": 7200,
                        "pool_info": {
                            "pool_name": "test",
                            "disk_status": "ONLINE",
                            "disk_read_errors": 0,
                            "disk_write_errors": 0,
                            "disk_checksum_errors": 0,
                            "vdev_name": "mirror-0",
                            "vdev_type": "data",
                            "vdev_disks": [
                                {
                                    "enclosure_id": "5b0bd6d1a30714bf",
                                    "slot": 1,
                                    "dev": "sda"
                                },
                                {
                                    "enclosure_id": "5b0bd6d1a30714bf",
                                    "slot": 2,
                                    "dev": "sdb"
                                },
                                {
                                    "enclosure_id": "5b0bd6d1a30714bf",
                                    "slot": 3,
                                    "dev": "sdc"
                                }
                            ]
                        }
                    }
                }
            }
        }]
        """
        return self.dashboard_impl()
