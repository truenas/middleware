from middlewared.schema import accepts, returns, List, Dict
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
    @returns(List('enclosures', items=[Dict('enclosure', additional_attrs=True)], example=[
        {
            "name": "iX 4024Sp e001",
            "model": "M60",
            "controller": True,
            "dmi": "TRUENAS-M60-HA",
            "status": [
                "OK"
            ],
            "id": "5b0bd6d1a309b57f",
            "vendor": "iX",
            "product": "4024Sp",
            "revision": "e001",
            "bsg": "/dev/bsg/17:0:19:0",
            "sg": "/dev/sg433",
            "pci": "17:0:19:0",
            "rackmount": True,
            "top_loaded": False,
            "front_slots": 24,
            "rear_slots": 4,
            "internal_slots": 0,
            "elements": {
                "Array Device Slot": {
                    "1": {
                        "descriptor": "slot00",
                        "status": "OK",
                        "dev": "sdadl",
                        "pool_info": None
                    },
                    "2": {
                        "descriptor": "slot01",
                        "status": "OK",
                        "dev": "sdadn",
                        "pool_info": None
                    },
                    "3": {
                        "descriptor": "slot02",
                        "status": "OK",
                        "dev": "sdado",
                        "pool_info": None
                    },
                    "4": {
                        "descriptor": "slot03",
                        "status": "OK",
                        "dev": "sdadq",
                        "pool_info": None
                    },
                    "5": {
                        "descriptor": "slot04",
                        "status": "OK",
                        "dev": "sdads",
                        "pool_info": None
                    },
                    "6": {
                        "descriptor": "slot05",
                        "status": "OK",
                        "dev": "sdadw",
                        "pool_info": None
                    },
                    "7": {
                        "descriptor": "slot06",
                        "status": "OK",
                        "dev": "sdadx",
                        "pool_info": None
                    },
                    "8": {
                        "descriptor": "slot07",
                        "status": "OK",
                        "dev": "sdady",
                        "pool_info": None
                    },
                    "9": {
                        "descriptor": "slot08",
                        "status": "OK",
                        "dev": "sdadz",
                        "pool_info": None
                    },
                    "10": {
                        "descriptor": "slot09",
                        "status": "OK",
                        "dev": "sdaec",
                        "pool_info": None
                    },
                    "11": {
                        "descriptor": "slot10",
                        "status": "OK",
                        "dev": "sdaed",
                        "pool_info": None
                    },
                    "12": {
                        "descriptor": "slot11",
                        "status": "OK",
                        "dev": "sdaee",
                        "pool_info": None
                    },
                    "13": {
                        "descriptor": "slot12",
                        "status": "OK",
                        "dev": "sdaem",
                        "pool_info": None
                    },
                    "14": {
                        "descriptor": "slot13",
                        "status": "OK",
                        "dev": "sdaen",
                        "pool_info": None
                    },
                    "15": {
                        "descriptor": "slot14",
                        "status": "OK",
                        "dev": "sdaeo",
                        "pool_info": None
                    },
                    "16": {
                        "descriptor": "slot15",
                        "status": "OK",
                        "dev": "sdaep",
                        "pool_info": None
                    },
                    "17": {
                        "descriptor": "slot16",
                        "status": "OK",
                        "dev": "sdaeu",
                        "pool_info": None
                    },
                    "18": {
                        "descriptor": "slot17",
                        "status": "OK",
                        "dev": "sdaev",
                        "pool_info": None
                    },
                    "19": {
                        "descriptor": "slot18",
                        "status": "OK",
                        "dev": "sdaew",
                        "pool_info": None
                    },
                    "20": {
                        "descriptor": "slot19",
                        "status": "Not installed",
                        "dev": None,
                        "pool_info": None
                    },
                    "21": {
                        "descriptor": "slot20",
                        "status": "Not installed",
                        "dev": None,
                        "pool_info": None
                    },
                    "22": {
                        "descriptor": "slot21",
                        "status": "Not installed",
                        "dev": None,
                        "pool_info": None
                    },
                    "23": {
                        "descriptor": "slot22",
                        "status": "Not installed",
                        "dev": None,
                        "pool_info": None
                    },
                    "24": {
                        "descriptor": "slot23",
                        "status": "Not installed",
                        "dev": None,
                        "pool_info": None
                    },
                    "25": {
                        "descriptor": "Disk #1",
                        "status": "Not installed",
                        "dev": None,
                        "pool_info": None
                    },
                    "26": {
                        "descriptor": "Disk #2",
                        "status": "OK",
                        "dev": "nvme1n1",
                        "pool_info": None
                    },
                    "27": {
                        "descriptor": "Disk #3",
                        "status": "OK",
                        "dev": "nvme2n1",
                        "pool_info": None
                    },
                    "28": {
                        "descriptor": "Disk #4",
                        "status": "OK",
                        "dev": "nvme3n1",
                        "pool_info": None
                    }
                },
                "SAS Expander": {
                    "26": {
                        "descriptor": "SAS3 Expander",
                        "status": "OK",
                        "value": None,
                        "value_raw": 16777216
                    }
                },
                "Enclosure": {
                    "28": {
                        "descriptor": "Encl-BpP",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672
                    },
                    "29": {
                        "descriptor": "Encl-PeerS",
                        "status": "OK",
                        "value": None,
                        "value_raw": 16777216
                    }
                },
                "Temperature Sensors": {
                    "31": {
                        "descriptor": "ExpP-Die",
                        "status": "OK",
                        "value": "36C",
                        "value_raw": 16791552
                    },
                    "32": {
                        "descriptor": "ExpS-Die",
                        "status": "OK",
                        "value": "36C",
                        "value_raw": 16791552
                    },
                    "33": {
                        "descriptor": "Sense BP1",
                        "status": "OK",
                        "value": "21C",
                        "value_raw": 16787712
                    },
                    "34": {
                        "descriptor": "Sense BP2",
                        "status": "OK",
                        "value": "21C",
                        "value_raw": 16787712
                    }
                },
                "Voltage Sensor": {
                    "36": {
                        "descriptor": "5V Sensor",
                        "status": "OK",
                        "value": "5.11V",
                        "value_raw": 16777727
                    },
                    "37": {
                        "descriptor": "12V Sensor",
                        "status": "OK",
                        "value": "12.44V",
                        "value_raw": 16778460
                    }
                }
            },
            "label": "iX 4024Sp e001"
        }
    ]))
    def dashboard(self):
        return self.dashboard_impl()
