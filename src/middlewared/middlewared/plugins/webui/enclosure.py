from middlewared.schema import accepts
from middlewared.service import Service


class WebUIEnclosureService(Service):
    class Config:
        namespace = 'webui.enclosure'
        private = True
        cli_private = True

    def dashboard_impl(self):
        disks_to_pools = dict()
        enclosures = self.middleware.call_sync('enclosure2.query')
        if enclosures:
            disks_to_pools = self.middleware.call_sync('zpool.status', {'real_paths': True})
            for enc in enclosures:
                for disk_slot, slot_info in enc['elements']['Array Device Slot'].items():
                    # remove some values that webUI doesn't use
                    slot_info.pop('original')
                    slot_info.pop('value')
                    slot_info.pop('value_raw')
                    pool_info = None
                    if slot_info['dev'] and (pool_info := disks_to_pools['disks'].get(slot_info['dev'])):
                        try:
                            index = pool_info['vdev_disks'].index(slot_info['dev'])
                            pool_info['vdev_disks'][index] = {
                                'enclosure_id': enc['id'],
                                'slot': int(disk_slot),
                                'dev': slot_info['dev'],
                            }
                        except ValueError:
                            # it means the disk's status in zfs land != ONLINE
                            # (i.e. it could be OFFLINE) and so it won't show
                            # up in the `vdev_disks` key, so it's best to catch
                            # this error and still append the disk to the list
                            # The `pool_info['disk_status']` key will be added
                            # which will give more insight into what's going on
                            pool_info['vdev_disks'].append({
                                'enclosure_id': enc['id'],
                                'slot': int(disk_slot),
                                'dev': slot_info['dev'],
                            })

                    slot_info.update({'pool_info': pool_info})

        return enclosures

    @accepts()
    def dashboard(self):
        """This endpoint is used exclusively by the webUI team for
        the enclosure dashboard page for iX sold hardware.

        An example of what this returns looks like the following:
            (NOTE: some redundant information cut out for brevity)
                [{
                    "id": "f60_nvme_enclosure",
                    "dmi": "f60_nvme_enclosure",
                    "model": "F60",
                    "sg": null,
                    "bsg": null,
                    "name": "F60 NVMe Enclosure",
                    "controller": true,
                    "status": [
                      "OK"
                    ],
                    "elements": {
                      "Array Device Slot": {
                        "1": {
                          "descriptor": "Disk #1",
                          "status": "OK",
                          "dev": "nvme3n1",
                          "pool_info": {
                            "pool_name": "sanity",
                            "disk_status": "ONLINE",
                            "vdev_name": "mirror-0",
                            "vdev_type": "data",
                            "vdev_disks": [
                              {
                                "enclosure_id": "f60_nvme_enclosure",
                                "slot": 1,
                                "dev": "nvme3n1"
                              },
                              {
                                "enclosure_id": "f60_nvme_enclosure",
                                "slot": 2,
                                "dev": "nvme1n1"
                              }
                            ]
                          }
                        },
                        "2": {
                          "descriptor": "Disk #2",
                          "status": "OK",
                          "dev": "nvme1n1",
                          "pool_info": {
                            "pool_name": "sanity",
                            "disk_status": "OFFLINE",
                            "vdev_name": "mirror-0",
                            "vdev_type": "data",
                            "vdev_disks": [
                              {
                                "enclosure_id": "f60_nvme_enclosure",
                                "slot": 1,
                                "dev": "nvme3n1"
                              },
                              {
                                "enclosure_id": "f60_nvme_enclosure",
                                "slot": 2,
                                "dev": "nvme1n1"
                              }
                            ]
                          }
                        },
                    }]
        """
        return self.dashboard_impl()
