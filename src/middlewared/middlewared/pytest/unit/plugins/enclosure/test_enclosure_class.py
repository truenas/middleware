from unittest.mock import patch

import pytest

from middlewared.plugins.enclosure_.enclosure_class import Enclosure


@pytest.mark.parametrize('data', [
    (
        {  # H10 head-unit libsg3.ses.EnclosureDevice.status() output
            'id': '3b0ad6d1c00007c0',
            'name': 'BROADCOMVirtualSES03',
            'status': {'OK'},
            'elements': {
                0: {'type': 23, 'descriptor': '<empty>', 'status': [0, 0, 0, 0]},
                1: {'type': 23, 'descriptor': '<empty>', 'status': [5, 0, 0, 0]},
                2: {'type': 23, 'descriptor': '<empty>', 'status': [5, 0, 0, 0]},
                3: {'type': 23, 'descriptor': '<empty>', 'status': [1, 0, 0, 0]},
                4: {'type': 23, 'descriptor': '<empty>', 'status': [5, 0, 0, 0]},
                5: {'type': 23, 'descriptor': '<empty>', 'status': [0, 0, 0, 0]},
                6: {'type': 23, 'descriptor': '<empty>', 'status': [0, 0, 0, 0]},
                7: {'type': 23, 'descriptor': '<empty>', 'status': [0, 0, 0, 0]},
                8: {'type': 23, 'descriptor': '<empty>', 'status': [0, 0, 0, 0]},
                9: {'type': 23, 'descriptor': '<empty>', 'status': [5, 0, 0, 0]},
                10: {'type': 23, 'descriptor': '<empty>', 'status': [5, 0, 0, 0]},
                11: {'type': 23, 'descriptor': '<empty>', 'status': [5, 0, 0, 0]},
                12: {'type': 23, 'descriptor': '<empty>', 'status': [5, 0, 0, 0]},
                13: {'type': 23, 'descriptor': '<empty>', 'status': [5, 0, 0, 0]},
                14: {'type': 23, 'descriptor': '<empty>', 'status': [1, 0, 0, 0]},
                15: {'type': 23, 'descriptor': '<empty>', 'status': [1, 0, 0, 0]},
                16: {'type': 23, 'descriptor': '<empty>', 'status': [1, 0, 0, 0]},
                17: {'type': 25, 'descriptor': '<empty>', 'status': [1, 0, 0, 0]},
                18: {'type': 25, 'descriptor': 'C1.0', 'status': [1, 0, 0, 0]},
                19: {'type': 25, 'descriptor': 'C1.0', 'status': [1, 0, 0, 0]},
                20: {'type': 25, 'descriptor': 'C1.0', 'status': [1, 0, 0, 0]},
                21: {'type': 25, 'descriptor': 'C1.0', 'status': [1, 0, 0, 0]},
                22: {'type': 25, 'descriptor': '<empty>', 'status': [5, 0, 0, 0]},
                23: {'type': 25, 'descriptor': '<empty>', 'status': [5, 0, 0, 0]},
                24: {'type': 25, 'descriptor': '<empty>', 'status': [5, 0, 0, 0]},
                25: {'type': 25, 'descriptor': '<empty>', 'status': [5, 0, 0, 0]},
                26: {'type': 25, 'descriptor': 'C1.1', 'status': [1, 0, 0, 0]},
                27: {'type': 25, 'descriptor': 'C1.1', 'status': [1, 0, 0, 0]},
                28: {'type': 25, 'descriptor': 'C1.1', 'status': [1, 0, 0, 0]},
                29: {'type': 25, 'descriptor': 'C1.1', 'status': [1, 0, 0, 0]},
                30: {'type': 25, 'descriptor': 'C1.2', 'status': [1, 0, 0, 0]},
                31: {'type': 25, 'descriptor': 'C1.2', 'status': [1, 0, 0, 0]},
                32: {'type': 25, 'descriptor': 'C1.2', 'status': [1, 0, 0, 0]},
                33: {'type': 25, 'descriptor': 'C1.2', 'status': [1, 0, 0, 0]}
            }
        },
        {  # H10 head-unit expected enclosure_class.py::Enclosure().asdict() output
            "name": "BROADCOM VirtualSES 03",
            "model": "H10",
            "controller": True,
            "dmi": "TRUENAS-H10-HA",
            "status": ["OK"],
            "id": "3b0ad6d1c00007c0",
            "vendor": "BROADCOM",
            "product": "VirtualSES",
            "revision": "03",
            "bsg": "/dev/bsg/0:0:0:0",
            "sg": "/dev/sg1",
            "pci": "0:0:0:0",
            "elements": {
                "Array Device Slot": {
                    "1": {"descriptor": "<empty>", "status": "Not installed", "value": None, "value_raw": 83886080, "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0", "enclosure_sg": "/dev/sg1", "enclosure_bsg": "/dev/bsg/0:0:0:0", "descriptor": "slot9", "slot": 9
                        }},
                    "2": {"descriptor": "<empty>", "status": "Not installed", "value": None, "value_raw": 83886080, "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0", "enclosure_sg": "/dev/sg1", "enclosure_bsg": "/dev/bsg/0:0:0:0", "descriptor": "slot10", "slot": 10
                        }},
                    "3": {"descriptor": "<empty>", "status": "Not installed", "value": None, "value_raw": 83886080, "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0", "enclosure_sg": "/dev/sg1", "enclosure_bsg": "/dev/bsg/0:0:0:0", "descriptor": "slot11", "slot": 11
                        }},
                    "4": {"descriptor": "<empty>", "status": "Not installed", "value": None, "value_raw": 83886080, "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0", "enclosure_sg": "/dev/sg1", "enclosure_bsg": "/dev/bsg/0:0:0:0", "descriptor": "slot12", "slot": 12
                        }},
                    "5": {"descriptor": "<empty>", "status": "Not installed", "value": None, "value_raw": 83886080, "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0", "enclosure_sg": "/dev/sg1", "enclosure_bsg": "/dev/bsg/0:0:0:0", "descriptor": "slot13", "slot": 13
                        }},
                    "6": {"descriptor": "<empty>", "status": "OK", "value": None, "value_raw": 16777216, "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0", "enclosure_sg": "/dev/sg1", "enclosure_bsg": "/dev/bsg/0:0:0:0", "descriptor": "slot14", "slot": 14
                        }},
                    "7": {"descriptor": "<empty>", "status": "OK", "value": None, "value_raw": 16777216, "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0", "enclosure_sg": "/dev/sg1", "enclosure_bsg": "/dev/bsg/0:0:0:0", "descriptor": "slot15", "slot": 15
                        }},
                    "8": {"descriptor": "<empty>", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sda",
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0", "enclosure_sg": "/dev/sg1", "enclosure_bsg": "/dev/bsg/0:0:0:0", "descriptor": "slot16", "slot": 16
                        }},
                    "9": {"descriptor": "<empty>", "status": "Not installed", "value": None, "value_raw": 83886080, "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0", "enclosure_sg": "/dev/sg1", "enclosure_bsg": "/dev/bsg/0:0:0:0", "descriptor": "slot1", "slot": 1
                        }},
                    "10": {"descriptor": "<empty>", "status": "Not installed", "value": None, "value_raw": 83886080, "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0", "enclosure_sg": "/dev/sg1", "enclosure_bsg": "/dev/bsg/0:0:0:0", "descriptor": "slot2", "slot": 2
                        }},
                    "11": {"descriptor": "<empty>", "status": "OK", "value": None, "value_raw": 16777216, "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0", "enclosure_sg": "/dev/sg1", "enclosure_bsg": "/dev/bsg/0:0:0:0", "descriptor": "slot3", "slot": 3
                        }},
                    "12": {"descriptor": "<empty>", "status": "Not installed", "value": None, "value_raw": 83886080, "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0", "enclosure_sg": "/dev/sg1", "enclosure_bsg": "/dev/bsg/0:0:0:0", "descriptor": "slot4", "slot": 4
                        }}
                },
                "SAS Connector": {
                    "17": {"descriptor": "<empty>", "status": "OK", "value": "No information", "value_raw": 16777216},
                    "18": {"descriptor": "C1.0", "status": "OK", "value": "No information", "value_raw": 16777216},
                    "19": {"descriptor": "C1.0", "status": "OK", "value": "No information", "value_raw": 16777216},
                    "20": {"descriptor": "C1.0", "status": "OK", "value": "No information", "value_raw": 16777216},
                    "21": {"descriptor": "C1.0", "status": "OK", "value": "No information", "value_raw": 16777216},
                    "22": {"descriptor": "<empty>", "status": "Not installed", "value": "No information", "value_raw": 83886080},
                    "23": {"descriptor": "<empty>", "status": "Not installed", "value": "No information", "value_raw": 83886080},
                    "24": {"descriptor": "<empty>", "status": "Not installed", "value": "No information", "value_raw": 83886080},
                    "25": {"descriptor": "<empty>", "status": "Not installed", "value": "No information", "value_raw": 83886080},
                    "26": {"descriptor": "C1.1", "status": "OK", "value": "No information", "value_raw": 16777216},
                    "27": {"descriptor": "C1.1", "status": "OK", "value": "No information", "value_raw": 16777216},
                    "28": {"descriptor": "C1.1", "status": "OK", "value": "No information", "value_raw": 16777216},
                    "29": {"descriptor": "C1.1", "status": "OK", "value": "No information", "value_raw": 16777216},
                    "30": {"descriptor": "C1.2", "status": "OK", "value": "No information", "value_raw": 16777216},
                    "31": {"descriptor": "C1.2", "status": "OK", "value": "No information", "value_raw": 16777216},
                    "32": {"descriptor": "C1.2", "status": "OK", "value": "No information", "value_raw": 16777216},
                    "33": {"descriptor": "C1.2", "status": "OK", "value": "No information", "value_raw": 16777216}
                },
                "label": "BROADCOM VirtualSES 03"
            }
        },
        {  # for mocking sysfs directory structure
            7: 'sda', 5: None, 11: None, 3: None, 9: None, 0: None, 6: None, 4: None, 10: None, 2: None, 8: None, 1: None
        }
    ),
    (
        {  # M60 head-unit libsg3.ses.EnclosureDevice.status() output
            'id': '5b0bd6d1a309b57f',
            'name': 'iX 4024Sp e001',
            'status': {'OK'},
            'elements': {
                0: {'type': 23, 'descriptor': 'ArrayDevices', 'status': [0, 0, 0, 0]},
                1: {'type': 23, 'descriptor': 'slot00       ', 'status': [1, 0, 0, 0]},
                2: {'type': 23, 'descriptor': 'slot01       ', 'status': [1, 0, 0, 0]},
                3: {'type': 23, 'descriptor': 'slot02       ', 'status': [1, 0, 0, 0]},
                4: {'type': 23, 'descriptor': 'slot03       ', 'status': [1, 0, 0, 0]},
                5: {'type': 23, 'descriptor': 'slot04       ', 'status': [1, 0, 0, 0]},
                6: {'type': 23, 'descriptor': 'slot05       ', 'status': [1, 0, 0, 0]},
                7: {'type': 23, 'descriptor': 'slot06       ', 'status': [1, 0, 0, 0]},
                8: {'type': 23, 'descriptor': 'slot07       ', 'status': [1, 0, 0, 0]},
                9: {'type': 23, 'descriptor': 'slot08       ', 'status': [1, 0, 0, 0]},
                10: {'type': 23, 'descriptor': 'slot09       ', 'status': [1, 0, 0, 0]},
                11: {'type': 23, 'descriptor': 'slot10       ', 'status': [1, 0, 0, 0]},
                12: {'type': 23, 'descriptor': 'slot11       ', 'status': [1, 0, 0, 0]},
                13: {'type': 23, 'descriptor': 'slot12       ', 'status': [1, 0, 0, 0]},
                14: {'type': 23, 'descriptor': 'slot13       ', 'status': [1, 0, 0, 0]},
                15: {'type': 23, 'descriptor': 'slot14       ', 'status': [1, 0, 0, 0]},
                16: {'type': 23, 'descriptor': 'slot15       ', 'status': [1, 0, 0, 0]},
                17: {'type': 23, 'descriptor': 'slot16       ', 'status': [1, 0, 0, 0]},
                18: {'type': 23, 'descriptor': 'slot17       ', 'status': [1, 0, 0, 0]},
                19: {'type': 23, 'descriptor': 'slot18       ', 'status': [1, 0, 0, 0]},
                20: {'type': 23, 'descriptor': 'slot19       ', 'status': [5, 0, 0, 0]},
                21: {'type': 23, 'descriptor': 'slot20       ', 'status': [5, 0, 0, 0]},
                22: {'type': 23, 'descriptor': 'slot21       ', 'status': [5, 0, 0, 0]},
                23: {'type': 23, 'descriptor': 'slot22       ', 'status': [5, 0, 0, 0]},
                24: {'type': 23, 'descriptor': 'slot23       ', 'status': [5, 0, 0, 0]},
                25: {'type': 24, 'descriptor': 'H24R-3X.R2D (LSISAS35Exp)', 'status': [0, 0, 0, 0]},
                26: {'type': 24, 'descriptor': 'SAS3 Expander', 'status': [1, 0, 0, 0]},
                27: {'type': 14, 'descriptor': 'EnclosureElement', 'status': [0, 0, 0, 0]},
                28: {'type': 14, 'descriptor': 'Encl-BpP', 'status': [17, 0, 0, 0]},
                29: {'type': 14, 'descriptor': 'Encl-PeerS', 'status': [1, 0, 0, 0]},
                30: {'type': 4, 'descriptor': 'NoSystemCool        ', 'status': [0, 0, 0, 0]},
                31: {'type': 4, 'descriptor': 'ExpP-Die   ', 'status': [1, 0, 55, 0]},
                32: {'type': 4, 'descriptor': 'ExpS-Die   ', 'status': [1, 0, 55, 0]},
                33: {'type': 4, 'descriptor': 'Sense BP1  ', 'status': [1, 0, 40, 0]},
                34: {'type': 4, 'descriptor': 'Sense BP2  ', 'status': [1, 0, 41, 0]},
                35: {'type': 18, 'descriptor': 'VoltageSensors', 'status': [0, 0, 0, 0]},
                36: {'type': 18, 'descriptor': '5V Sensor   ', 'status': [1, 0, 1, 255]},
                37: {'type': 18, 'descriptor': '12V Sensor  ', 'status': [1, 0, 4, 219]}
            }
        },
        {  # M60 head-unit expected enclosure_class.py::Enclosure().asdict() output
            "name": "iX 4024Sp e001",
            "model": "M60",
            "controller": True,
            "dmi": "TRUENAS-M60-HA",
            "status": ["OK"],
            "id": "5b0bd6d1a309b57f",
            "vendor": "iX",
            "product": "4024Sp",
            "revision": "e001",
            "bsg": "/dev/bsg/17:0:19:0",
            "sg": "/dev/sg433",
            "pci": "17:0:19:0",
            "elements": {
                "Array Device Slot": {
                    "1": {"descriptor": "slot00", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdact",
                          "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot1", "slot": 1}
                    },
                    "2": {"descriptor": "slot01", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdyv",
                          "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot2", "slot": 2}
                    },
                    "3": {"descriptor": "slot02", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdyy",
                          "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot3", "slot": 3}
                    },
                    "4": {"descriptor": "slot03", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdadc",
                          "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot4", "slot": 4}
                    },
                    "5": {"descriptor": "slot04", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdyz",
                          "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot5", "slot": 5}
                    },
                    "6": {"descriptor": "slot05", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdzb",
                          "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot6", "slot": 6}
                    },
                    "7": {"descriptor": "slot06", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdzd",
                          "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot7", "slot": 7}
                    },
                    "8": {"descriptor": "slot07", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdze",
                          "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot8", "slot": 8}
                    },
                    "9": {"descriptor": "slot08", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdzh",
                          "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot9", "slot": 9}
                    },
                    "10": {"descriptor": "slot09", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdzj",
                           "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot10", "slot": 10}
                    },
                    "11": {"descriptor": "slot10", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdzo",
                           "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot11", "slot": 11}
                    },
                    "12": {"descriptor": "slot11", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdzp",
                           "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot12", "slot": 12}
                    },
                    "13": {"descriptor": "slot12", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdzs",
                           "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot13", "slot": 13}
                    },
                    "14": {"descriptor": "slot13", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdzv",
                           "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot14", "slot": 14}
                    },
                    "15": {"descriptor": "slot14", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdzy",
                           "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot15", "slot": 15}
                    },
                    "16": {"descriptor": "slot15", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdaab", 
                           "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot16", "slot": 16}
                    },
                    "17": {"descriptor": "slot16", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdaae",
                           "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot17", "slot": 17}
                    },
                    "18": {"descriptor": "slot17", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdaah",
                           "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot18", "slot": 18}
                    },
                    "19": {"descriptor": "slot18", "status": "OK", "value": None, "value_raw": 16777216, "dev": "sdaai",
                           "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot19", "slot": 19}
                    },
                    "20": {"descriptor": "slot19", "status": "Not installed", "value": None, "value_raw": 83886080, "dev": None,
                           "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot20", "slot": 20}
                    },
                    "21": {"descriptor": "slot20", "status": "Not installed", "value": None, "value_raw": 83886080, "dev": None,
                           "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot21", "slot": 21}
                    },
                    "22": {"descriptor": "slot21", "status": "Not installed", "value": None, "value_raw": 83886080, "dev": None,
                           "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot22", "slot": 22}
                    },
                    "23": {"descriptor": "slot22", "status": "Not installed", "value": None, "value_raw": 83886080, "dev": None,
                           "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot23", "slot": 23}
                    },
                    "24": {"descriptor": "slot23", "status": "Not installed", "value": None, "value_raw": 83886080, "dev": None,
                           "original": {"enclosure_id": "5b0bd6d1a309b57f", "enclosure_sg": "/dev/sg433", "enclosure_bsg": "/dev/bsg/17:0:19:0", "descriptor": "slot24", "slot": 24}
                    },
                    "25": {"descriptor": "Disk #1", "status": "Not installed", "value": None, "value_raw": 83886080, "dev": None,
                           "original": {"enclosure_id": "m60_nvme_enclosure", "enclosure_sg": None, "enclosure_bsg": None, "descriptor": "slot1", "slot": 1}
                    },
                    "26": {"descriptor": "Disk #2", "status": "OK", "value": None, "value_raw": 16777216, "dev": "nvme1n1",
                           "original": {"enclosure_id": "m60_nvme_enclosure", "enclosure_sg": None, "enclosure_bsg": None, "descriptor": "slot2", "slot": 2}
                    },
                    "27": {"descriptor": "Disk #3", "status": "OK", "value": None, "value_raw": 16777216, "dev": "nvme2n1",
                           "original": {"enclosure_id": "m60_nvme_enclosure", "enclosure_sg": None, "enclosure_bsg": None, "descriptor": "slot3", "slot": 3}
                    },
                    "28": {"descriptor": "Disk #4", "status": "OK", "value": None, "value_raw": 16777216, "dev": "nvme3n1",
                           "original": {"enclosure_id": "m60_nvme_enclosure", "enclosure_sg": None, "enclosure_bsg": None, "descriptor": "slot4", "slot": 4}
                    }
                },
                "SAS Expander": {
                    "26": {"descriptor": "SAS3 Expander", "status": "OK", "value": None, "value_raw": 16777216}
                },
                "Enclosure": {
                    "28": {"descriptor": "Encl-BpP", "status": "OK, Swapped", "value": None, "value_raw": 285212672},
                    "29": {"descriptor": "Encl-PeerS", "status": "OK", "value": None, "value_raw": 16777216}
                },
                "Temperature Sensors": {
                    "31": {"descriptor": "ExpP-Die", "status": "OK", "value": "37C", "value_raw": 16791808},
                    "32": {"descriptor": "ExpS-Die", "status": "OK", "value": "36C", "value_raw": 16791552},
                    "33": {"descriptor": "Sense BP1", "status": "OK", "value": "22C", "value_raw": 16787968},
                    "34": {"descriptor": "Sense BP2", "status": "OK", "value": "22C", "value_raw": 16787968}
                },
                "Voltage Sensor": {
                    "36": {"descriptor": "5V Sensor", "status": "OK", "value": "5.12V", "value_raw": 16777728},
                    "37": {"descriptor": "12V Sensor", "status": "OK", "value": "12.45V", "value_raw": 16778461}
                }
            },
            "label": "iX 4024Sp e001"
        },
    ),
    (
        {  # ES102 JBOD libsg3.ses.EnclosureDevice.status() output
            'id': '5000ccab05114080',
            'name': 'HGSTH4102-J3010',
            'status': {'INFO'},
            'elements': {
                0: {'type': 23, 'descriptor': '<empty>', 'status': [17, 0, 0, 0]},
                1: {'type': 23, 'descriptor': 'SLOT 000,3FHY4B1T           ', 'status': [17, 0, 0, 0]},
                2: {'type': 23, 'descriptor': 'SLOT 001,3FHYW56T           ', 'status': [17, 0, 0, 0]},
                3: {'type': 23, 'descriptor': 'SLOT 002,3FHVU2ET           ', 'status': [1, 0, 0, 0]},
                4: {'type': 23, 'descriptor': 'SLOT 003,3FHUW53T           ', 'status': [17, 0, 0, 0]},
                5: {'type': 23, 'descriptor': 'SLOT 004,3FGZD37T           ', 'status': [17, 0, 0, 0]},
                6: {'type': 23, 'descriptor': 'SLOT 005,3FHYY0KT           ', 'status': [17, 0, 0, 0]},
                7: {'type': 23, 'descriptor': 'SLOT 006,3FHXKYKT           ', 'status': [17, 0, 0, 0]},
                8: {'type': 23, 'descriptor': 'SLOT 007,3FHDSPZT           ', 'status': [17, 0, 0, 0]},
                9: {'type': 23, 'descriptor': 'SLOT 008,3FHPELZT           ', 'status': [17, 0, 0, 0]},
                10: {'type': 23, 'descriptor': 'SLOT 009,3FHY7VTT           ', 'status': [17, 0, 0, 0]},
                11: {'type': 23, 'descriptor': 'SLOT 010,3FHYGWZT           ', 'status': [17, 0, 0, 0]},
                12: {'type': 23, 'descriptor': 'SLOT 011,3FHY82MT           ', 'status': [17, 0, 0, 0]},
                13: {'type': 23, 'descriptor': 'SLOT 012,3FHY7TST           ', 'status': [17, 0, 0, 0]},
                14: {'type': 23, 'descriptor': 'SLOT 013,3FHXJY1T           ', 'status': [17, 0, 0, 0]},
                15: {'type': 23, 'descriptor': 'SLOT 014,3JGAVUTG           ', 'status': [17, 0, 0, 0]},
                16: {'type': 23, 'descriptor': 'SLOT 015,3FHWJ3PT           ', 'status': [17, 0, 0, 0]},
                17: {'type': 23, 'descriptor': 'SLOT 016,3FHY8D9T           ', 'status': [17, 0, 0, 0]},
                18: {'type': 23, 'descriptor': 'SLOT 017,3FHWJ34T           ', 'status': [17, 0, 0, 0]},
                19: {'type': 23, 'descriptor': 'SLOT 018,3FHX9AYT           ', 'status': [17, 0, 0, 0]},
                20: {'type': 23, 'descriptor': 'SLOT 019,3FHPPSZT           ', 'status': [17, 0, 0, 0]},
                21: {'type': 23, 'descriptor': 'SLOT 020,3FHXK9LT           ', 'status': [17, 0, 0, 0]},
                22: {'type': 23, 'descriptor': 'SLOT 021,3FHXGU1T           ', 'status': [17, 0, 0, 0]},
                23: {'type': 23, 'descriptor': 'SLOT 022,3FHX884T           ', 'status': [17, 0, 0, 0]},
                24: {'type': 23, 'descriptor': 'SLOT 023,3FHZULBT           ', 'status': [17, 0, 0, 0]},
                25: {'type': 23, 'descriptor': 'SLOT 024,3FHMYD3T           ', 'status': [17, 0, 0, 0]},
                26: {'type': 23, 'descriptor': 'SLOT 025,3FHYWRLT           ', 'status': [1, 0, 0, 0]},
                27: {'type': 23, 'descriptor': 'SLOT 026,3FHY7HKT           ', 'status': [17, 0, 0, 0]},
                28: {'type': 23, 'descriptor': 'SLOT 027,3FH53KVT           ', 'status': [17, 0, 0, 0]},
                29: {'type': 23, 'descriptor': 'SLOT 028,3FHVV2MT           ', 'status': [17, 0, 0, 0]},
                30: {'type': 23, 'descriptor': 'SLOT 029,3FHYYDMT           ', 'status': [17, 0, 0, 0]},
                31: {'type': 23, 'descriptor': 'SLOT 030,3FHY8DUT           ', 'status': [17, 0, 0, 0]},
                32: {'type': 23, 'descriptor': 'SLOT 031,3FHVV6MT           ', 'status': [17, 0, 0, 0]},
                33: {'type': 23, 'descriptor': 'SLOT 032,3FHXH4ZT           ', 'status': [17, 0, 0, 0]},
                34: {'type': 23, 'descriptor': 'SLOT 033,3FHY9BTT           ', 'status': [17, 0, 0, 0]},
                35: {'type': 23, 'descriptor': 'SLOT 034,3FHYZL6T           ', 'status': [17, 0, 0, 0]},
                36: {'type': 23, 'descriptor': 'SLOT 035,3FHVY5DT           ', 'status': [17, 0, 0, 0]},
                37: {'type': 23, 'descriptor': 'SLOT 036,3FHY7YVT           ', 'status': [17, 0, 0, 0]},
                38: {'type': 23, 'descriptor': 'SLOT 037,3FHP8HVT           ', 'status': [17, 0, 0, 0]},
                39: {'type': 23, 'descriptor': 'SLOT 038,3FHL2GVT           ', 'status': [17, 0, 0, 0]},
                40: {'type': 23, 'descriptor': 'SLOT 039,3FHYELJT           ', 'status': [17, 0, 0, 0]},
                41: {'type': 23, 'descriptor': 'SLOT 040,3FHXK3AT           ', 'status': [17, 0, 0, 0]},
                42: {'type': 23, 'descriptor': 'SLOT 041,3FHY794T           ', 'status': [17, 0, 0, 0]},
                43: {'type': 23, 'descriptor': 'SLOT 042,3FHY7ZMT           ', 'status': [17, 0, 0, 0]},
                44: {'type': 23, 'descriptor': 'SLOT 043,3FHXJPZT           ', 'status': [17, 0, 0, 0]},
                45: {'type': 23, 'descriptor': 'SLOT 044,3FHYYKZT           ', 'status': [17, 0, 0, 0]},
                46: {'type': 23, 'descriptor': 'SLOT 045,3FG5WWGT           ', 'status': [17, 0, 0, 0]},
                47: {'type': 23, 'descriptor': 'SLOT 046,3FHVY5ET           ', 'status': [17, 0, 0, 0]},
                48: {'type': 23, 'descriptor': 'SLOT 047,3FHY8K0T           ', 'status': [17, 0, 0, 0]},
                49: {'type': 23, 'descriptor': 'SLOT 048,3FHP8MUT           ', 'status': [17, 0, 0, 0]},
                50: {'type': 23, 'descriptor': 'SLOT 049,3FHSK4TT           ', 'status': [17, 0, 0, 0]},
                51: {'type': 23, 'descriptor': 'SLOT 050,3FHYEU8T           ', 'status': [17, 0, 0, 0]},
                52: {'type': 23, 'descriptor': 'SLOT 051,3FHXKTBT           ', 'status': [17, 0, 0, 0]},
                53: {'type': 23, 'descriptor': 'SLOT 052,3FHYT3KT           ', 'status': [17, 0, 0, 0]},
                54: {'type': 23, 'descriptor': 'SLOT 053,3FH9KXKT           ', 'status': [17, 0, 0, 0]},
                55: {'type': 23, 'descriptor': 'SLOT 054,3FHWJ11T           ', 'status': [17, 0, 0, 0]},
                56: {'type': 23, 'descriptor': 'SLOT 055,3FHP9LAT           ', 'status': [17, 0, 0, 0]},
                57: {'type': 23, 'descriptor': 'SLOT 056,3FHYWADT           ', 'status': [17, 0, 0, 0]},
                58: {'type': 23, 'descriptor': 'SLOT 057,3FHX9EYT           ', 'status': [17, 0, 0, 0]},
                59: {'type': 23, 'descriptor': 'SLOT 058,3FHNHMKT           ', 'status': [17, 0, 0, 0]},
                60: {'type': 23, 'descriptor': 'SLOT 059,3FHY881T           ', 'status': [17, 0, 0, 0]},
                61: {'type': 23, 'descriptor': 'SLOT 060,3FHWKYDT           ', 'status': [17, 0, 0, 0]},
                62: {'type': 23, 'descriptor': 'SLOT 061,3FHXKUET           ', 'status': [17, 0, 0, 0]},
                63: {'type': 23, 'descriptor': 'SLOT 062,3FHYEDST           ', 'status': [17, 0, 0, 0]},
                64: {'type': 23, 'descriptor': 'SLOT 063,3FGNW33T           ', 'status': [17, 0, 0, 0]},
                65: {'type': 23, 'descriptor': 'SLOT 064,3FHWJBGT           ', 'status': [17, 0, 0, 0]},
                66: {'type': 23, 'descriptor': 'SLOT 065,3FHYWSPT           ', 'status': [17, 0, 0, 0]},
                67: {'type': 23, 'descriptor': 'SLOT 066,3FHXWBST           ', 'status': [17, 0, 0, 0]},
                68: {'type': 23, 'descriptor': 'SLOT 067,3FHVUBJT           ', 'status': [17, 0, 0, 0]},
                69: {'type': 23, 'descriptor': 'SLOT 068,3FHWJK6T           ', 'status': [17, 0, 0, 0]},
                70: {'type': 23, 'descriptor': 'SLOT 069,3FHWHJET           ', 'status': [17, 0, 0, 0]},
                71: {'type': 23, 'descriptor': 'SLOT 070,3FHY9KZT           ', 'status': [17, 0, 0, 0]},
                72: {'type': 23, 'descriptor': 'SLOT 071,3FHWMJ6T           ', 'status': [17, 0, 0, 0]},
                73: {'type': 23, 'descriptor': 'SLOT 072,3FHX9V4T           ', 'status': [17, 0, 0, 0]},
                74: {'type': 23, 'descriptor': 'SLOT 073,3FHXKNHT           ', 'status': [17, 0, 0, 0]},
                75: {'type': 23, 'descriptor': 'SLOT 074,3FHP5NLT           ', 'status': [17, 0, 0, 0]},
                76: {'type': 23, 'descriptor': 'SLOT 075,3FHNZNJT           ', 'status': [17, 0, 0, 0]},
                77: {'type': 23, 'descriptor': 'SLOT 076,3FHY8NWT           ', 'status': [17, 0, 0, 0]},
                78: {'type': 23, 'descriptor': 'SLOT 077,3FHXHGGT           ', 'status': [17, 0, 0, 0]},
                79: {'type': 23, 'descriptor': 'SLOT 078,3FHYSYPT           ', 'status': [17, 0, 0, 0]},
                80: {'type': 23, 'descriptor': 'SLOT 079,3FHYT0RT           ', 'status': [17, 0, 0, 0]},
                81: {'type': 23, 'descriptor': 'SLOT 080,3FHY8BST           ', 'status': [17, 0, 0, 0]},
                82: {'type': 23, 'descriptor': 'SLOT 081,3FHWJ6RT           ', 'status': [17, 0, 0, 0]},
                83: {'type': 23, 'descriptor': 'SLOT 082,3FHR0T8T           ', 'status': [17, 0, 0, 0]},
                84: {'type': 23, 'descriptor': 'SLOT 083,3FHP590T           ', 'status': [17, 0, 0, 0]},
                85: {'type': 23, 'descriptor': 'SLOT 084,3FH4KZKT           ', 'status': [17, 0, 0, 0]},
                86: {'type': 23, 'descriptor': 'SLOT 085,3FHMU2RT           ', 'status': [17, 0, 0, 0]},
                87: {'type': 23, 'descriptor': 'SLOT 086,3FHW9ZUT           ', 'status': [17, 0, 0, 0]},
                88: {'type': 23, 'descriptor': 'SLOT 087,3FHYYHKT           ', 'status': [1, 0, 0, 0]},
                89: {'type': 23, 'descriptor': 'SLOT 088,3FHWB62T           ', 'status': [17, 0, 0, 0]},
                90: {'type': 23, 'descriptor': 'SLOT 089,3FHY9AST           ', 'status': [17, 0, 0, 0]},
                91: {'type': 23, 'descriptor': 'SLOT 090,3FHP60UT           ', 'status': [17, 0, 0, 0]},
                92: {'type': 23, 'descriptor': 'SLOT 091,3FHYH15T           ', 'status': [17, 0, 0, 0]},
                93: {'type': 23, 'descriptor': 'SLOT 092,3FHPX1MT           ', 'status': [17, 0, 0, 0]},
                94: {'type': 23, 'descriptor': 'SLOT 093,3FHZN54T           ', 'status': [17, 0, 0, 0]},
                95: {'type': 23, 'descriptor': 'SLOT 094,3FHY8HDT           ', 'status': [17, 0, 0, 0]},
                96: {'type': 23, 'descriptor': 'SLOT 095,3FHVY5BT           ', 'status': [17, 0, 0, 0]},
                97: {'type': 23, 'descriptor': 'SLOT 096,3FHP4TJT           ', 'status': [17, 0, 0, 0]},
                98: {'type': 23, 'descriptor': 'SLOT 097,3FHD4Z0T           ', 'status': [17, 0, 0, 0]},
                99: {'type': 23, 'descriptor': 'SLOT 098,3FHV2HBT           ', 'status': [17, 0, 0, 0]},
                100: {'type': 23, 'descriptor': 'SLOT 099,3FHYS3XT           ', 'status': [17, 0, 0, 0]},
                101: {'type': 23, 'descriptor': 'SLOT 100,3FHG1Y7T           ', 'status': [17, 0, 0, 0]},
                102: {'type': 23, 'descriptor': 'SLOT 101,3FHY8N4T           ', 'status': [17, 0, 0, 0]},
                103: {'type': 14, 'descriptor': '<empty>', 'status': [1, 0, 0, 0]},
                104: {'type': 14, 'descriptor': 'ENCLOSURE,1ES1846-A3,THCCT03821EA008E,1EB1173-A1,THCCT03721EJ1979                                                           ', 'status': [1, 0, 0, 0]},
                105: {'type': 2, 'descriptor': '<empty>', 'status': [1, 0, 0, 160]},
                106: {'type': 2, 'descriptor': 'POWER SUPPLY A,CSU1800AP-3-10,N8681X00DPAKZ,,Artesyn,1800W                                  ', 'status': [1, 0, 0, 160]},
                107: {'type': 2, 'descriptor': 'POWER SUPPLY B,CSU1800AP-3-10,N8681X004TAKZ,,Artesyn,1800W                                  ', 'status': [1, 0, 0, 160]},
                108: {'type': 3, 'descriptor': '<empty>', 'status': [1, 0, 0, 160]},
                109: {'type': 3, 'descriptor': 'FAN ENCL 1      ', 'status': [1, 1, 145, 162]},
                110: {'type': 3, 'descriptor': 'FAN ENCL 2      ', 'status': [1, 1, 145, 162]},
                111: {'type': 3, 'descriptor': 'FAN ENCL 3      ', 'status': [1, 1, 149, 162]},
                112: {'type': 3, 'descriptor': 'FAN ENCL 4      ', 'status': [1, 1, 146, 162]},
                113: {'type': 3, 'descriptor': 'FAN IOM 1       ', 'status': [1, 7, 74, 166]},
                114: {'type': 3, 'descriptor': 'FAN IOM 2       ', 'status': [1, 6, 78, 166]},
                115: {'type': 3, 'descriptor': 'FAN PSU A       ', 'status': [1, 7, 255, 166]},
                116: {'type': 3, 'descriptor': 'FAN PSU B       ', 'status': [1, 7, 255, 166]},
                117: {'type': 4, 'descriptor': '<empty>', 'status': [17, 0, 0, 0]},
                118: {'type': 4, 'descriptor': 'TEMP SLOT 000   ', 'status': [17, 0, 46, 0]},
                119: {'type': 4, 'descriptor': 'TEMP SLOT 001   ', 'status': [17, 0, 45, 0]},
                120: {'type': 4, 'descriptor': 'TEMP SLOT 002   ', 'status': [1, 0, 45, 0]},
                121: {'type': 4, 'descriptor': 'TEMP SLOT 003   ', 'status': [17, 0, 45, 0]},
                122: {'type': 4, 'descriptor': 'TEMP SLOT 004   ', 'status': [17, 0, 45, 0]},
                123: {'type': 4, 'descriptor': 'TEMP SLOT 005   ', 'status': [17, 0, 45, 0]},
                124: {'type': 4, 'descriptor': 'TEMP SLOT 006   ', 'status': [17, 0, 45, 0]},
                125: {'type': 4, 'descriptor': 'TEMP SLOT 007   ', 'status': [17, 0, 45, 0]},
                126: {'type': 4, 'descriptor': 'TEMP SLOT 008   ', 'status': [17, 0, 46, 0]},
                127: {'type': 4, 'descriptor': 'TEMP SLOT 009   ', 'status': [17, 0, 46, 0]},
                128: {'type': 4, 'descriptor': 'TEMP SLOT 010   ', 'status': [17, 0, 46, 0]},
                129: {'type': 4, 'descriptor': 'TEMP SLOT 011   ', 'status': [17, 0, 46, 0]},
                130: {'type': 4, 'descriptor': 'TEMP SLOT 012   ', 'status': [17, 0, 46, 0]},
                131: {'type': 4, 'descriptor': 'TEMP SLOT 013   ', 'status': [17, 0, 46, 0]},
                132: {'type': 4, 'descriptor': 'TEMP SLOT 014   ', 'status': [17, 0, 51, 0]},
                133: {'type': 4, 'descriptor': 'TEMP SLOT 015   ', 'status': [17, 0, 52, 0]},
                134: {'type': 4, 'descriptor': 'TEMP SLOT 016   ', 'status': [17, 0, 52, 0]},
                135: {'type': 4, 'descriptor': 'TEMP SLOT 017   ', 'status': [17, 0, 52, 0]},
                136: {'type': 4, 'descriptor': 'TEMP SLOT 018   ', 'status': [17, 0, 52, 0]},
                137: {'type': 4, 'descriptor': 'TEMP SLOT 019   ', 'status': [17, 0, 52, 0]},
                138: {'type': 4, 'descriptor': 'TEMP SLOT 020   ', 'status': [17, 0, 52, 0]},
                139: {'type': 4, 'descriptor': 'TEMP SLOT 021   ', 'status': [17, 0, 51, 0]},
                140: {'type': 4, 'descriptor': 'TEMP SLOT 022   ', 'status': [17, 0, 52, 0]},
                141: {'type': 4, 'descriptor': 'TEMP SLOT 023   ', 'status': [17, 0, 53, 0]},
                142: {'type': 4, 'descriptor': 'TEMP SLOT 024   ', 'status': [17, 0, 53, 0]},
                143: {'type': 4, 'descriptor': 'TEMP SLOT 025   ', 'status': [1, 0, 53, 0]},
                144: {'type': 4, 'descriptor': 'TEMP SLOT 026   ', 'status': [17, 0, 52, 0]},
                145: {'type': 4, 'descriptor': 'TEMP SLOT 027   ', 'status': [17, 0, 52, 0]},
                146: {'type': 4, 'descriptor': 'TEMP SLOT 028   ', 'status': [17, 0, 55, 0]},
                147: {'type': 4, 'descriptor': 'TEMP SLOT 029   ', 'status': [17, 0, 57, 0]},
                148: {'type': 4, 'descriptor': 'TEMP SLOT 030   ', 'status': [17, 0, 58, 0]},
                149: {'type': 4, 'descriptor': 'TEMP SLOT 031   ', 'status': [17, 0, 58, 0]},
                150: {'type': 4, 'descriptor': 'TEMP SLOT 032   ', 'status': [17, 0, 58, 0]},
                151: {'type': 4, 'descriptor': 'TEMP SLOT 033   ', 'status': [17, 0, 58, 0]},
                152: {'type': 4, 'descriptor': 'TEMP SLOT 034   ', 'status': [17, 0, 56, 0]},
                153: {'type': 4, 'descriptor': 'TEMP SLOT 035   ', 'status': [17, 0, 56, 0]},
                154: {'type': 4, 'descriptor': 'TEMP SLOT 036   ', 'status': [17, 0, 58, 0]},
                155: {'type': 4, 'descriptor': 'TEMP SLOT 037   ', 'status': [17, 0, 58, 0]},
                156: {'type': 4, 'descriptor': 'TEMP SLOT 038   ', 'status': [17, 0, 59, 0]},
                157: {'type': 4, 'descriptor': 'TEMP SLOT 039   ', 'status': [17, 0, 58, 0]},
                158: {'type': 4, 'descriptor': 'TEMP SLOT 040   ', 'status': [17, 0, 58, 0]},
                159: {'type': 4, 'descriptor': 'TEMP SLOT 041   ', 'status': [17, 0, 56, 0]},
                160: {'type': 4, 'descriptor': 'TEMP SLOT 042   ', 'status': [17, 0, 56, 0]},
                161: {'type': 4, 'descriptor': 'TEMP SLOT 043   ', 'status': [17, 0, 61, 0]},
                162: {'type': 4, 'descriptor': 'TEMP SLOT 044   ', 'status': [17, 0, 62, 0]},
                163: {'type': 4, 'descriptor': 'TEMP SLOT 045   ', 'status': [17, 0, 63, 0]},
                164: {'type': 4, 'descriptor': 'TEMP SLOT 046   ', 'status': [17, 0, 63, 0]},
                165: {'type': 4, 'descriptor': 'TEMP SLOT 047   ', 'status': [17, 0, 61, 0]},
                166: {'type': 4, 'descriptor': 'TEMP SLOT 048   ', 'status': [17, 0, 61, 0]},
                167: {'type': 4, 'descriptor': 'TEMP SLOT 049   ', 'status': [17, 0, 64, 0]},
                168: {'type': 4, 'descriptor': 'TEMP SLOT 050   ', 'status': [17, 0, 64, 0]},
                169: {'type': 4, 'descriptor': 'TEMP SLOT 051   ', 'status': [17, 0, 63, 0]},
                170: {'type': 4, 'descriptor': 'TEMP SLOT 052   ', 'status': [17, 0, 62, 0]},
                171: {'type': 4, 'descriptor': 'TEMP SLOT 053   ', 'status': [17, 0, 58, 0]},
                172: {'type': 4, 'descriptor': 'TEMP SLOT 054   ', 'status': [17, 0, 59, 0]},
                173: {'type': 4, 'descriptor': 'TEMP SLOT 055   ', 'status': [17, 0, 59, 0]},
                174: {'type': 4, 'descriptor': 'TEMP SLOT 056   ', 'status': [17, 0, 59, 0]},
                175: {'type': 4, 'descriptor': 'TEMP SLOT 057   ', 'status': [17, 0, 58, 0]},
                176: {'type': 4, 'descriptor': 'TEMP SLOT 058   ', 'status': [17, 0, 57, 0]},
                177: {'type': 4, 'descriptor': 'TEMP SLOT 059   ', 'status': [17, 0, 54, 0]},
                178: {'type': 4, 'descriptor': 'TEMP SLOT 060   ', 'status': [17, 0, 53, 0]},
                179: {'type': 4, 'descriptor': 'TEMP SLOT 061   ', 'status': [17, 0, 56, 0]},
                180: {'type': 4, 'descriptor': 'TEMP SLOT 062   ', 'status': [17, 0, 58, 0]},
                181: {'type': 4, 'descriptor': 'TEMP SLOT 063   ', 'status': [17, 0, 59, 0]},
                182: {'type': 4, 'descriptor': 'TEMP SLOT 064   ', 'status': [17, 0, 59, 0]},
                183: {'type': 4, 'descriptor': 'TEMP SLOT 065   ', 'status': [17, 0, 59, 0]},
                184: {'type': 4, 'descriptor': 'TEMP SLOT 066   ', 'status': [17, 0, 62, 0]},
                185: {'type': 4, 'descriptor': 'TEMP SLOT 067   ', 'status': [17, 0, 64, 0]},
                186: {'type': 4, 'descriptor': 'TEMP SLOT 068   ', 'status': [17, 0, 65, 0]},
                187: {'type': 4, 'descriptor': 'TEMP SLOT 069   ', 'status': [17, 0, 65, 0]},
                188: {'type': 4, 'descriptor': 'TEMP SLOT 070   ', 'status': [17, 0, 64, 0]},
                189: {'type': 4, 'descriptor': 'TEMP SLOT 071   ', 'status': [17, 0, 62, 0]},
                190: {'type': 4, 'descriptor': 'TEMP SLOT 072   ', 'status': [17, 0, 60, 0]},
                191: {'type': 4, 'descriptor': 'TEMP SLOT 073   ', 'status': [17, 0, 63, 0]},
                192: {'type': 4, 'descriptor': 'TEMP SLOT 074   ', 'status': [17, 0, 65, 0]},
                193: {'type': 4, 'descriptor': 'TEMP SLOT 075   ', 'status': [17, 0, 65, 0]},
                194: {'type': 4, 'descriptor': 'TEMP SLOT 076   ', 'status': [17, 0, 65, 0]},
                195: {'type': 4, 'descriptor': 'TEMP SLOT 077   ', 'status': [17, 0, 64, 0]},
                196: {'type': 4, 'descriptor': 'TEMP SLOT 078   ', 'status': [17, 0, 64, 0]},
                197: {'type': 4, 'descriptor': 'TEMP SLOT 079   ', 'status': [17, 0, 68, 0]},
                198: {'type': 4, 'descriptor': 'TEMP SLOT 080   ', 'status': [17, 0, 69, 0]},
                199: {'type': 4, 'descriptor': 'TEMP SLOT 081   ', 'status': [17, 0, 70, 0]},
                200: {'type': 4, 'descriptor': 'TEMP SLOT 082   ', 'status': [17, 0, 70, 0]},
                201: {'type': 4, 'descriptor': 'TEMP SLOT 083   ', 'status': [17, 0, 67, 0]},
                202: {'type': 4, 'descriptor': 'TEMP SLOT 084   ', 'status': [17, 0, 65, 0]},
                203: {'type': 4, 'descriptor': 'TEMP SLOT 085   ', 'status': [17, 0, 69, 0]},
                204: {'type': 4, 'descriptor': 'TEMP SLOT 086   ', 'status': [17, 0, 69, 0]},
                205: {'type': 4, 'descriptor': 'TEMP SLOT 087   ', 'status': [1, 0, 70, 0]},
                206: {'type': 4, 'descriptor': 'TEMP SLOT 088   ', 'status': [17, 0, 69, 0]},
                207: {'type': 4, 'descriptor': 'TEMP SLOT 089   ', 'status': [17, 0, 66, 0]},
                208: {'type': 4, 'descriptor': 'TEMP SLOT 090   ', 'status': [17, 0, 63, 0]},
                209: {'type': 4, 'descriptor': 'TEMP SLOT 091   ', 'status': [17, 0, 67, 0]},
                210: {'type': 4, 'descriptor': 'TEMP SLOT 092   ', 'status': [17, 0, 68, 0]},
                211: {'type': 4, 'descriptor': 'TEMP SLOT 093   ', 'status': [17, 0, 69, 0]},
                212: {'type': 4, 'descriptor': 'TEMP SLOT 094   ', 'status': [17, 0, 69, 0]},
                213: {'type': 4, 'descriptor': 'TEMP SLOT 095   ', 'status': [17, 0, 68, 0]},
                214: {'type': 4, 'descriptor': 'TEMP SLOT 096   ', 'status': [17, 0, 65, 0]},
                215: {'type': 4, 'descriptor': 'TEMP SLOT 097   ', 'status': [17, 0, 68, 0]},
                216: {'type': 4, 'descriptor': 'TEMP SLOT 098   ', 'status': [17, 0, 69, 0]},
                217: {'type': 4, 'descriptor': 'TEMP SLOT 099   ', 'status': [17, 0, 69, 0]},
                218: {'type': 4, 'descriptor': 'TEMP SLOT 100   ', 'status': [17, 0, 68, 0]},
                219: {'type': 4, 'descriptor': 'TEMP SLOT 101   ', 'status': [17, 0, 65, 0]},
                220: {'type': 4, 'descriptor': 'TEMP IOM A      ', 'status': [1, 0, 70, 0]},
                221: {'type': 4, 'descriptor': 'TEMP IOM B      ', 'status': [1, 0, 74, 0]},
                222: {'type': 4, 'descriptor': 'TEMP BB 60 1    ', 'status': [1, 0, 49, 0]},
                223: {'type': 4, 'descriptor': 'TEMP BB 60 2    ', 'status': [1, 0, 51, 0]},
                224: {'type': 4, 'descriptor': 'TEMP BB 42 1    ', 'status': [1, 0, 38, 0]},
                225: {'type': 4, 'descriptor': 'TEMP BB 42 2    ', 'status': [1, 0, 37, 0]},
                226: {'type': 4, 'descriptor': 'TEMP PRI A DIE  ', 'status': [1, 0, 79, 0]},
                227: {'type': 4, 'descriptor': 'TEMP SEC1 A DIE ', 'status': [1, 0, 98, 0]},
                228: {'type': 4, 'descriptor': 'TEMP SEC2 A DIE ', 'status': [1, 0, 84, 0]},
                229: {'type': 4, 'descriptor': 'TEMP PRI A MEM  ', 'status': [1, 0, 67, 0]},
                230: {'type': 4, 'descriptor': 'TEMP SEC1 A MEM ', 'status': [1, 0, 67, 0]},
                231: {'type': 4, 'descriptor': 'TEMP SEC2 A MEM ', 'status': [1, 0, 61, 0]},
                232: {'type': 4, 'descriptor': 'TEMP PRI B DIE  ', 'status': [1, 0, 79, 0]},
                233: {'type': 4, 'descriptor': 'TEMP SEC1 B DIE ', 'status': [1, 0, 104, 0]},
                234: {'type': 4, 'descriptor': 'TEMP SEC2 B DIE ', 'status': [1, 0, 90, 0]},
                235: {'type': 4, 'descriptor': 'TEMP PRI B MEM  ', 'status': [1, 0, 70, 0]},
                236: {'type': 4, 'descriptor': 'TEMP SEC1 B MEM ', 'status': [1, 0, 73, 0]},
                237: {'type': 4, 'descriptor': 'TEMP SEC2 B MEM ', 'status': [1, 0, 63, 0]},
                238: {'type': 4, 'descriptor': 'TEMP IOM A 5V   ', 'status': [1, 0, 73, 0]},
                239: {'type': 4, 'descriptor': 'TEMP IOM B 5V   ', 'status': [1, 0, 67, 0]},
                240: {'type': 4, 'descriptor': 'TEMP PSU A AMB  ', 'status': [1, 0, 57, 0]},
                241: {'type': 4, 'descriptor': 'TEMP PSU A HOT  ', 'status': [1, 0, 68, 0]},
                242: {'type': 4, 'descriptor': 'TEMP PSU A PRI  ', 'status': [1, 0, 63, 0]},
                243: {'type': 4, 'descriptor': 'TEMP PSU B AMB  ', 'status': [1, 0, 55, 0]},
                244: {'type': 4, 'descriptor': 'TEMP PSU B HOT  ', 'status': [1, 0, 68, 0]},
                245: {'type': 4, 'descriptor': 'TEMP PSU B PRI  ', 'status': [1, 0, 63, 0]},
                246: {'type': 7, 'descriptor': '<empty>', 'status': [1, 0, 1, 128]},
                247: {'type': 7, 'descriptor': 'ESCE IOMA,1EA0484-C1          ,THCCT03821EG00F9    ,5000CCAB051140BC,,00:0C:CA:07:44:54,3.1.11                                                              ', 'status': [1, 16, 1, 128]},
                248: {'type': 7, 'descriptor': 'ESCE IOMB,1EA0484-C1          ,THCCT03821EG00FA    ,5000CCAB051140FC,,00:0C:CA:07:44:55,3.1.11                                                              ', 'status': [1, 16, 0, 128]},
                249: {'type': 24, 'descriptor': '<empty>', 'status': [1, 0, 0, 0]},
                250: {'type': 24, 'descriptor': 'EXP IOMA 0,3010-007,5000CCAB051140BD', 'status': [1, 0, 0, 0]},
                251: {'type': 24, 'descriptor': 'EXP IOMA 1,3010-007,5000CCAB051140BF', 'status': [1, 0, 0, 0]},
                252: {'type': 24, 'descriptor': 'EXP IOMA 2,3010-007,5000CCAB051140FF', 'status': [1, 0, 0, 0]},
                253: {'type': 24, 'descriptor': 'EXP IOMB 0,3010-007,5000CCAB051140FD', 'status': [1, 0, 0, 0]},
                254: {'type': 24, 'descriptor': 'EXP IOMB 1,3010-007,5000CCAB051140F9', 'status': [1, 0, 0, 0]},
                255: {'type': 24, 'descriptor': 'EXP IOMB 2,3010-007,5000CCAB051140FB', 'status': [1, 0, 0, 0]},
                256: {'type': 25, 'descriptor': '<empty>', 'status': [5, 0, 0, 0]},
                257: {'type': 25, 'descriptor': 'CONN HOST 00    ', 'status': [1, 5, 255, 128]},
                258: {'type': 25, 'descriptor': 'CONN HOST 01    ', 'status': [5, 5, 255, 0]},
                259: {'type': 25, 'descriptor': 'CONN HOST 02    ', 'status': [5, 5, 255, 0]},
                260: {'type': 25, 'descriptor': 'CONN HOST 03    ', 'status': [5, 5, 255, 0]},
                261: {'type': 25, 'descriptor': 'CONN HOST 04    ', 'status': [5, 5, 255, 0]},
                262: {'type': 25, 'descriptor': 'CONN HOST 05    ', 'status': [5, 5, 255, 0]},
                263: {'type': 25, 'descriptor': 'CONN HOST 06    ', 'status': [1, 5, 255, 128]},
                264: {'type': 25, 'descriptor': 'CONN HOST 07    ', 'status': [5, 5, 255, 0]},
                265: {'type': 25, 'descriptor': 'CONN HOST 08    ', 'status': [5, 5, 255, 0]},
                266: {'type': 25, 'descriptor': 'CONN HOST 09    ', 'status': [5, 5, 255, 0]},
                267: {'type': 25, 'descriptor': 'CONN HOST 10    ', 'status': [5, 5, 255, 0]},
                268: {'type': 25, 'descriptor': 'CONN HOST 11    ', 'status': [5, 5, 255, 0]},
                269: {'type': 18, 'descriptor': '<empty>', 'status': [1, 0, 0, 0]},
                270: {'type': 18, 'descriptor': 'VOLT PSU A AC   ', 'status': [1, 0, 78, 32]},
                271: {'type': 18, 'descriptor': 'VOLT PSU A 12V  ', 'status': [1, 0, 4, 205]},
                272: {'type': 18, 'descriptor': 'VOLT PSU B AC   ', 'status': [1, 0, 79, 76]},
                273: {'type': 18, 'descriptor': 'VOLT PSU B 12V  ', 'status': [1, 0, 4, 199]},
                274: {'type': 18, 'descriptor': 'VOLT IOM A 5V   ', 'status': [1, 0, 1, 247]},
                275: {'type': 18, 'descriptor': 'VOLT IOM A 12V  ', 'status': [1, 0, 4, 176]},
                276: {'type': 18, 'descriptor': 'VOLT IOM B 5V   ', 'status': [1, 0, 1, 247]},
                277: {'type': 18, 'descriptor': 'VOLT IOM B 12V  ', 'status': [1, 0, 4, 176]},
                278: {'type': 19, 'descriptor': '<empty>', 'status': [1, 0, 0, 0]},
                279: {'type': 19, 'descriptor': 'CURR PSU A IN   ', 'status': [1, 0, 0, 219]},
                280: {'type': 19, 'descriptor': 'CURR PSU A OUT  ', 'status': [1, 0, 12, 166]},
                281: {'type': 19, 'descriptor': 'CURR PSU B IN   ', 'status': [1, 0, 0, 219]},
                282: {'type': 19, 'descriptor': 'CURR PSU B OUT  ', 'status': [1, 0, 12, 216]},
                283: {'type': 19, 'descriptor': 'CURR IOM A 12V  ', 'status': [1, 0, 6, 57]},
                284: {'type': 19, 'descriptor': 'CURR IOM A 5V   ', 'status': [1, 0, 9, 71]},
                285: {'type': 19, 'descriptor': 'CURR IOM B 12V  ', 'status': [1, 0, 5, 89]},
                286: {'type': 19, 'descriptor': 'CURR IOM B 5V   ', 'status': [1, 0, 7, 208]},
                287: {'type': 5, 'descriptor': '<empty>', 'status': [1, 0, 0, 0]},
                288: {'type': 5, 'descriptor': 'ENCLOSURE COVER ', 'status': [1, 0, 0, 0]}
            }
        },
        {  # ES102 JBOD enclosure_class.py::Enclosure.asdict() output
            'name': 'HGST H4102-J 3010',
            'model': 'ES102',
            'controller': False,
            'dmi': 'TRUENAS-M60-HA',
            'status': ['INFO'],
            'id': '5000ccab05114080',
            'vendor': 'HGST',
            'product': 'H4102-J',
            'revision': '3010',
            'bsg': '/dev/bsg/0:0:0:0',
            'sg': '/dev/sg2',
            'pci': '0:0:0:0',
            'elements': {
                'Array Device Slot': {
                    '1': {'descriptor': 'SLOT 000,3FHY4B1T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdkn',
                          'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot1', 'slot': 1}
                    },
                    '2': {'descriptor': 'SLOT 001,3FHYW56T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdko',
                          'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot2', 'slot': 2}
                    },
                    '3': {'descriptor': 'SLOT 002,3FHVU2ET', 'status': 'OK', 'value': None, 'value_raw': 16777216, 'dev': 'sdkp',
                          'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot3', 'slot': 3}
                    },
                    '4': {'descriptor': 'SLOT 003,3FHUW53T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdkq',
                          'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot4', 'slot': 4}
                    },
                    '5': {'descriptor': 'SLOT 004,3FGZD37T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdks',
                          'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot5', 'slot': 5}
                    },
                    '6': {'descriptor': 'SLOT 005,3FHYY0KT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdkt',
                          'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot6', 'slot': 6}
                    },
                    '7': {'descriptor': 'SLOT 006,3FHXKYKT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdku',
                          'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot7', 'slot': 7}
                    },
                    '8': {'descriptor': 'SLOT 007,3FHDSPZT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdkw',
                          'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot8', 'slot': 8}
                    },
                    '9': {'descriptor': 'SLOT 008,3FHPELZT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdla',
                          'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot9', 'slot': 9}
                    },
                    '10': {'descriptor': 'SLOT 009,3FHY7VTT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdkv',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot10', 'slot': 10}
                    },
                    '11': {'descriptor': 'SLOT 010,3FHYGWZT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdky',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot11', 'slot': 11}
                    },
                    '12': {'descriptor': 'SLOT 011,3FHY82MT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdlc',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot12', 'slot': 12}
                    },
                    '13': {'descriptor': 'SLOT 012,3FHY7TST', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdld',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot13', 'slot': 13}
                    },
                    '14': {'descriptor': 'SLOT 013,3FHXJY1T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdle',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot14', 'slot': 14}
                    },
                    '15': {'descriptor': 'SLOT 014,3JGAVUTG', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdlf',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot15', 'slot': 15}
                    },
                    '16': {'descriptor': 'SLOT 015,3FHWJ3PT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdlh',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot16', 'slot': 16}
                    },
                    '17': {'descriptor': 'SLOT 016,3FHY8D9T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdlg',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot17', 'slot': 17}
                    },
                    '18': {'descriptor': 'SLOT 017,3FHWJ34T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdlj',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot18', 'slot': 18}
                    },
                    '19': {'descriptor': 'SLOT 018,3FHX9AYT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdlm',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot19', 'slot': 19}
                    },
                    '20': {'descriptor': 'SLOT 019,3FHPPSZT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdll',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot20', 'slot': 20}
                    },
                    '21': {'descriptor': 'SLOT 020,3FHXK9LT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdln',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot21', 'slot': 21}
                    },
                    '22': {'descriptor': 'SLOT 021,3FHXGU1T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdlo',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot22', 'slot': 22}
                    },
                    '23': {'descriptor': 'SLOT 022,3FHX884T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdlq',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot23', 'slot': 23}
                    },
                    '24': {'descriptor': 'SLOT 023,3FHZULBT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdlr',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot24', 'slot': 24}
                    },
                    '25': {'descriptor': 'SLOT 024,3FHMYD3T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdls',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot25', 'slot': 25}
                    },
                    '26': {'descriptor': 'SLOT 025,3FHYWRLT', 'status': 'OK', 'value': None, 'value_raw': 16777216, 'dev': 'sdlu',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot26', 'slot': 26}
                    },
                    '27': {'descriptor': 'SLOT 026,3FHY7HKT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdlv',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot27', 'slot': 27}
                    },
                    '28': {'descriptor': 'SLOT 027,3FH53KVT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdlw',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot28', 'slot': 28}
                    },
                    '29': {'descriptor': 'SLOT 028,3FHVV2MT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdlz',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot29', 'slot': 29}
                    },
                    '30': {'descriptor': 'SLOT 029,3FHYYDMT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdma',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot30', 'slot': 30}
                    },
                    '31': {'descriptor': 'SLOT 030,3FHY8DUT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdmb',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot31', 'slot': 31}
                    },
                    '32': {'descriptor': 'SLOT 031,3FHVV6MT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdmf',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot32', 'slot': 32}
                    },
                    '33': {'descriptor': 'SLOT 032,3FHXH4ZT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdme',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot33', 'slot': 33}
                    },
                    '34': {'descriptor': 'SLOT 033,3FHY9BTT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdmh',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot34', 'slot': 34}
                    },
                    '35': {'descriptor': 'SLOT 034,3FHYZL6T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdmg',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot35', 'slot': 35}
                    },
                    '36': {'descriptor': 'SLOT 035,3FHVY5DT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdmi',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot36', 'slot': 36}
                    },
                    '37': {'descriptor': 'SLOT 036,3FHY7YVT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdmk',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot37', 'slot': 37}
                    },
                    '38': {'descriptor': 'SLOT 037,3FHP8HVT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdml',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot38', 'slot': 38}
                    },
                    '39': {'descriptor': 'SLOT 038,3FHL2GVT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdmm',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot39', 'slot': 39}
                    },
                    '40': {'descriptor': 'SLOT 039,3FHYELJT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdmo',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot40', 'slot': 40}
                    },
                    '41': {'descriptor': 'SLOT 040,3FHXK3AT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdmp',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot41', 'slot': 41}
                    },
                    '42': {'descriptor': 'SLOT 041,3FHY794T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdmq',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot42', 'slot': 42}
                    },
                    '43': {'descriptor': 'SLOT 042,3FHY7ZMT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdb',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot43', 'slot': 43}
                    },
                    '44': {'descriptor': 'SLOT 043,3FHXJPZT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdmr',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot44', 'slot': 44}
                    },
                    '45': {'descriptor': 'SLOT 044,3FHYYKZT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdg',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot45', 'slot': 45}
                    },
                    '46': {'descriptor': 'SLOT 045,3FG5WWGT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdmt',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot46', 'slot': 46}
                    },
                    '47': {'descriptor': 'SLOT 046,3FHVY5ET', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdmu',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot47', 'slot': 47}
                    },
                    '48': {'descriptor': 'SLOT 047,3FHY8K0T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdmv',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot48', 'slot': 48}
                    },
                    '49': {'descriptor': 'SLOT 048,3FHP8MUT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdmx',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot49', 'slot': 49}
                    },
                    '50': {'descriptor': 'SLOT 049,3FHSK4TT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdmz',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot50', 'slot': 50}
                    },
                    '51': {'descriptor': 'SLOT 050,3FHYEU8T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdna',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot51', 'slot': 51}
                    },
                    '52': {'descriptor': 'SLOT 051,3FHXKTBT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdnb',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot52', 'slot': 52}
                    },
                    '53': {'descriptor': 'SLOT 052,3FHYT3KT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdnc',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot53', 'slot': 53}
                    },
                    '54': {'descriptor': 'SLOT 053,3FH9KXKT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sde',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot54', 'slot': 54}
                    },
                    '55': {'descriptor': 'SLOT 054,3FHWJ11T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdf',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot55', 'slot': 55}
                    },
                    '56': {'descriptor': 'SLOT 055,3FHP9LAT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdh',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot56', 'slot': 56}
                    },
                    '57': {'descriptor': 'SLOT 056,3FHYWADT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sda',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot57', 'slot': 57}
                    },
                    '58': {'descriptor': 'SLOT 057,3FHX9EYT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdc',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot58', 'slot': 58}
                    },
                    '59': {'descriptor': 'SLOT 058,3FHNHMKT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdd',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot59', 'slot': 59}
                    },
                    '60': {'descriptor': 'SLOT 059,3FHY881T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdl',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot60', 'slot': 60}
                    }, 
                    '61': {'descriptor': 'SLOT 060,3FHWKYDT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdi',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot61', 'slot': 61}
                    },
                    '62': {'descriptor': 'SLOT 061,3FHXKUET', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdj',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot62', 'slot': 62}
                    },
                    '63': {'descriptor': 'SLOT 062,3FHYEDST', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdn',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot63', 'slot': 63}
                    },
                    '64': {'descriptor': 'SLOT 063,3FGNW33T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdk',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot64', 'slot': 64}
                    },
                    '65': {'descriptor': 'SLOT 064,3FHWJBGT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdo',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot65', 'slot': 65}
                    },
                    '66': {'descriptor': 'SLOT 065,3FHYWSPT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdm',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot66', 'slot': 66}
                    },
                    '67': {'descriptor': 'SLOT 066,3FHXWBST', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdae',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot67', 'slot': 67}
                    },
                    '68': {'descriptor': 'SLOT 067,3FHVUBJT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sds',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot68', 'slot': 68}
                    },
                    '69': {'descriptor': 'SLOT 068,3FHWJK6T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdad',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot69', 'slot': 69}
                    },
                    '70': {'descriptor': 'SLOT 069,3FHWHJET', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdv',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot70', 'slot': 70}
                    }, 
                    '71': {'descriptor': 'SLOT 070,3FHY9KZT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdy',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot71', 'slot': 71}
                    },
                    '72': {'descriptor': 'SLOT 071,3FHWMJ6T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdp',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot72', 'slot': 72}
                    },
                    '73': {'descriptor': 'SLOT 072,3FHX9V4T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdt',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot73', 'slot': 73}
                    },
                    '74': {'descriptor': 'SLOT 073,3FHXKNHT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdq',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot74', 'slot': 74}
                    },
                    '75': {'descriptor': 'SLOT 074,3FHP5NLT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdw',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot75', 'slot': 75}
                    },
                    '76': {'descriptor': 'SLOT 075,3FHNZNJT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdr',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot76', 'slot': 76}
                    },
                    '77': {'descriptor': 'SLOT 076,3FHY8NWT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdx',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot77', 'slot': 77}
                    },
                    '78': {'descriptor': 'SLOT 077,3FHXHGGT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdu',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot78', 'slot': 78}
                    },
                    '79': {'descriptor': 'SLOT 078,3FHYSYPT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdac',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot79', 'slot': 79}
                    },
                    '80': {'descriptor': 'SLOT 079,3FHYT0RT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdz',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot80', 'slot': 80}
                    },
                    '81': {'descriptor': 'SLOT 080,3FHY8BST', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdaa',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot81', 'slot': 81}
                    },
                    '82': {'descriptor': 'SLOT 081,3FHWJ6RT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdab',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot82', 'slot': 82}
                    },
                    '83': {'descriptor': 'SLOT 082,3FHR0T8T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdaf',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot83', 'slot': 83}
                    },
                    '84': {'descriptor': 'SLOT 083,3FHP590T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdbl',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot84', 'slot': 84}
                    },
                    '85': {'descriptor': 'SLOT 084,3FH4KZKT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdbn',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot85', 'slot': 85}
                    },
                    '86': {'descriptor': 'SLOT 085,3FHMU2RT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdbm', 
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot86', 'slot': 86}
                    },
                    '87': {'descriptor': 'SLOT 086,3FHW9ZUT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdcn',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot87', 'slot': 87}
                    },
                    '88': {'descriptor': 'SLOT 087,3FHYYHKT', 'status': 'OK', 'value': None, 'value_raw': 16777216, 'dev': 'sdbo',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot88', 'slot': 88}
                    },
                    '89': {'descriptor': 'SLOT 088,3FHWB62T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdbq',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot89', 'slot': 89}
                    },
                    '90': {'descriptor': 'SLOT 089,3FHY9AST', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdbr', 
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot90', 'slot': 90}
                    },
                    '91': {'descriptor': 'SLOT 090,3FHP60UT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdbx',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot91', 'slot': 91}
                    },
                    '92': {'descriptor': 'SLOT 091,3FHYH15T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdbz',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot92', 'slot': 92}
                    },
                    '93': {'descriptor': 'SLOT 092,3FHPX1MT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdbt',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot93', 'slot': 93}
                    },
                    '94': {'descriptor': 'SLOT 093,3FHZN54T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdby',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot94', 'slot': 94}
                    },
                    '95': {'descriptor': 'SLOT 094,3FHY8HDT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdcb',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot95', 'slot': 95}
                    },
                    '96': {'descriptor': 'SLOT 095,3FHVY5BT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sddy',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot96', 'slot': 96}
                    },
                    '97': {'descriptor': 'SLOT 096,3FHP4TJT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdcc',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot97', 'slot': 97}
                    },
                    '98': {'descriptor': 'SLOT 097,3FHD4Z0T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdci',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot98', 'slot': 98}
                    },
                    '99': {'descriptor': 'SLOT 098,3FHV2HBT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdcd',
                           'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot99', 'slot': 99}
                    },
                    '100': {'descriptor': 'SLOT 099,3FHYS3XT', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdck',
                            'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot100', 'slot': 100}
                    },
                    '101': {'descriptor': 'SLOT 100,3FHG1Y7T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sdda',
                            'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot101', 'slot': 101}
                    }, 
                    '102': {'descriptor': 'SLOT 101,3FHY8N4T', 'status': 'OK, Swapped', 'value': None, 'value_raw': 285212672, 'dev': 'sddu',
                            'original': {'enclosure_id': '5000ccab05114080', 'enclosure_sg': '/dev/sg2', 'enclosure_bsg': '/dev/bsg/0:0:0:0', 'descriptor': 'slot102', 'slot': 102}
                    }
                },
                'Enclosure': {
                    '104': {'descriptor': 'ENCLOSURE,1ES1846-A3,THCCT03821EA008E,1EB1173-A1,THCCT03721EJ1979', 'status': 'OK', 'value': None, 'value_raw': 16777216}
                },
                'Power Supply': {
                    '106': {'descriptor': 'POWER SUPPLY A,CSU1800AP-3-10,N8681X00DPAKZ,,Artesyn,1800W', 'status': 'OK', 'value': 'Hot swap, RQST on', 'value_raw': 16777376},
                    '107': {'descriptor': 'POWER SUPPLY B,CSU1800AP-3-10,N8681X004TAKZ,,Artesyn,1800W', 'status': 'OK', 'value': 'Hot swap, RQST on', 'value_raw': 16777376}
                },
                'Cooling': {
                    '109': {'descriptor': 'FAN ENCL 1', 'status': 'OK', 'value': '5720 RPM', 'value_raw': 16923811},
                    '110': {'descriptor': 'FAN ENCL 2', 'status': 'OK', 'value': '5730 RPM', 'value_raw': 16924067},
                    '111': {'descriptor': 'FAN ENCL 3', 'status': 'OK', 'value': '5690 RPM', 'value_raw': 16923043},
                    '112': {'descriptor': 'FAN ENCL 4', 'status': 'OK', 'value': '5740 RPM', 'value_raw': 16924323},
                    '113': {'descriptor': 'FAN IOM 1', 'status': 'OK', 'value': '15690 RPM', 'value_raw': 17179045},
                    '114': {'descriptor': 'FAN IOM 2', 'status': 'OK', 'value': '13670 RPM', 'value_raw': 17127333},
                    '115': {'descriptor': 'FAN PSU A', 'status': 'OK', 'value': '17730 RPM', 'value_raw': 17231269},
                    '116': {'descriptor': 'FAN PSU B', 'status': 'OK', 'value': '17950 RPM', 'value_raw': 17236901}
                },
                'Temperature Sensors': {
                    '118': {'descriptor': 'TEMP SLOT 000', 'status': 'OK, Swapped', 'value': '25C', 'value_raw': 285224192},
                    '119': {'descriptor': 'TEMP SLOT 001', 'status': 'OK, Swapped', 'value': '25C', 'value_raw': 285224192},
                    '120': {'descriptor': 'TEMP SLOT 002', 'status': 'OK', 'value': '25C', 'value_raw': 16788736},
                    '121': {'descriptor': 'TEMP SLOT 003', 'status': 'OK, Swapped', 'value': '25C', 'value_raw': 285224192},
                    '122': {'descriptor': 'TEMP SLOT 004', 'status': 'OK, Swapped', 'value': '25C', 'value_raw': 285224192},
                    '123': {'descriptor': 'TEMP SLOT 005', 'status': 'OK, Swapped', 'value': '25C', 'value_raw': 285224192},
                    '124': {'descriptor': 'TEMP SLOT 006', 'status': 'OK, Swapped', 'value': '25C', 'value_raw': 285224192},
                    '125': {'descriptor': 'TEMP SLOT 007', 'status': 'OK, Swapped', 'value': '25C', 'value_raw': 285224192},
                    '126': {'descriptor': 'TEMP SLOT 008', 'status': 'OK, Swapped', 'value': '25C', 'value_raw': 285224192},
                    '127': {'descriptor': 'TEMP SLOT 009', 'status': 'OK, Swapped', 'value': '26C', 'value_raw': 285224448},
                    '128': {'descriptor': 'TEMP SLOT 010', 'status': 'OK, Swapped', 'value': '26C', 'value_raw': 285224448},
                    '129': {'descriptor': 'TEMP SLOT 011', 'status': 'OK, Swapped', 'value': '26C', 'value_raw': 285224448},
                    '130': {'descriptor': 'TEMP SLOT 012', 'status': 'OK, Swapped', 'value': '26C', 'value_raw': 285224448},
                    '131': {'descriptor': 'TEMP SLOT 013', 'status': 'OK, Swapped', 'value': '26C', 'value_raw': 285224448},
                    '132': {'descriptor': 'TEMP SLOT 014', 'status': 'OK, Swapped', 'value': '30C', 'value_raw': 285225472},
                    '133': {'descriptor': 'TEMP SLOT 015', 'status': 'OK, Swapped', 'value': '31C', 'value_raw': 285225728},
                    '134': {'descriptor': 'TEMP SLOT 016', 'status': 'OK, Swapped', 'value': '31C', 'value_raw': 285225728},
                    '135': {'descriptor': 'TEMP SLOT 017', 'status': 'OK, Swapped', 'value': '31C', 'value_raw': 285225728},
                    '136': {'descriptor': 'TEMP SLOT 018', 'status': 'OK, Swapped', 'value': '31C', 'value_raw': 285225728},
                    '137': {'descriptor': 'TEMP SLOT 019', 'status': 'OK, Swapped', 'value': '31C', 'value_raw': 285225728},
                    '138': {'descriptor': 'TEMP SLOT 020', 'status': 'OK, Swapped', 'value': '31C', 'value_raw': 285225728},
                    '139': {'descriptor': 'TEMP SLOT 021', 'status': 'OK, Swapped', 'value': '31C', 'value_raw': 285225728},
                    '140': {'descriptor': 'TEMP SLOT 022', 'status': 'OK, Swapped', 'value': '31C', 'value_raw': 285225728},
                    '141': {'descriptor': 'TEMP SLOT 023', 'status': 'OK, Swapped', 'value': '32C', 'value_raw': 285225984},
                    '142': {'descriptor': 'TEMP SLOT 024', 'status': 'OK, Swapped', 'value': '32C', 'value_raw': 285225984},
                    '143': {'descriptor': 'TEMP SLOT 025', 'status': 'OK', 'value': '32C', 'value_raw': 16790528},
                    '144': {'descriptor': 'TEMP SLOT 026', 'status': 'OK, Swapped', 'value': '32C', 'value_raw': 285225984},
                    '145': {'descriptor': 'TEMP SLOT 027', 'status': 'OK, Swapped', 'value': '31C', 'value_raw': 285225728},
                    '146': {'descriptor': 'TEMP SLOT 028', 'status': 'OK, Swapped', 'value': '33C', 'value_raw': 285226240},
                    '147': {'descriptor': 'TEMP SLOT 029', 'status': 'OK, Swapped', 'value': '36C', 'value_raw': 285227008},
                    '148': {'descriptor': 'TEMP SLOT 030', 'status': 'OK, Swapped', 'value': '37C', 'value_raw': 285227264},
                    '149': {'descriptor': 'TEMP SLOT 031', 'status': 'OK, Swapped', 'value': '37C', 'value_raw': 285227264},
                    '150': {'descriptor': 'TEMP SLOT 032', 'status': 'OK, Swapped', 'value': '37C', 'value_raw': 285227264},
                    '151': {'descriptor': 'TEMP SLOT 033', 'status': 'OK, Swapped', 'value': '37C', 'value_raw': 285227264},
                    '152': {'descriptor': 'TEMP SLOT 034', 'status': 'OK, Swapped', 'value': '35C', 'value_raw': 285226752},
                    '153': {'descriptor': 'TEMP SLOT 035', 'status': 'OK, Swapped', 'value': '35C', 'value_raw': 285226752},
                    '154': {'descriptor': 'TEMP SLOT 036', 'status': 'OK, Swapped', 'value': '37C', 'value_raw': 285227264},
                    '155': {'descriptor': 'TEMP SLOT 037', 'status': 'OK, Swapped', 'value': '37C', 'value_raw': 285227264},
                    '156': {'descriptor': 'TEMP SLOT 038', 'status': 'OK, Swapped', 'value': '37C', 'value_raw': 285227264},
                    '157': {'descriptor': 'TEMP SLOT 039', 'status': 'OK, Swapped', 'value': '37C', 'value_raw': 285227264},
                    '158': {'descriptor': 'TEMP SLOT 040', 'status': 'OK, Swapped', 'value': '36C', 'value_raw': 285227008},
                    '159': {'descriptor': 'TEMP SLOT 041', 'status': 'OK, Swapped', 'value': '35C', 'value_raw': 285226752},
                    '160': {'descriptor': 'TEMP SLOT 042', 'status': 'OK, Swapped', 'value': '35C', 'value_raw': 285226752},
                    '161': {'descriptor': 'TEMP SLOT 043', 'status': 'OK, Swapped', 'value': '40C', 'value_raw': 285228032},
                    '162': {'descriptor': 'TEMP SLOT 044', 'status': 'OK, Swapped', 'value': '41C', 'value_raw': 285228288},
                    '163': {'descriptor': 'TEMP SLOT 045', 'status': 'OK, Swapped', 'value': '42C', 'value_raw': 285228544},
                    '164': {'descriptor': 'TEMP SLOT 046', 'status': 'OK, Swapped', 'value': '42C', 'value_raw': 285228544},
                    '165': {'descriptor': 'TEMP SLOT 047', 'status': 'OK, Swapped', 'value': '40C', 'value_raw': 285228032},
                    '166': {'descriptor': 'TEMP SLOT 048', 'status': 'OK, Swapped', 'value': '40C', 'value_raw': 285228032},
                    '167': {'descriptor': 'TEMP SLOT 049', 'status': 'OK, Swapped', 'value': '42C', 'value_raw': 285228544},
                    '168': {'descriptor': 'TEMP SLOT 050', 'status': 'OK, Swapped', 'value': '43C', 'value_raw': 285228800},
                    '169': {'descriptor': 'TEMP SLOT 051', 'status': 'OK, Swapped', 'value': '42C', 'value_raw': 285228544},
                    '170': {'descriptor': 'TEMP SLOT 052', 'status': 'OK, Swapped', 'value': '40C', 'value_raw': 285228032},
                    '171': {'descriptor': 'TEMP SLOT 053', 'status': 'OK, Swapped', 'value': '37C', 'value_raw': 285227264},
                    '172': {'descriptor': 'TEMP SLOT 054', 'status': 'OK, Swapped', 'value': '37C', 'value_raw': 285227264},
                    '173': {'descriptor': 'TEMP SLOT 055', 'status': 'OK, Swapped', 'value': '37C', 'value_raw': 285227264},
                    '174': {'descriptor': 'TEMP SLOT 056', 'status': 'OK, Swapped', 'value': '38C', 'value_raw': 285227520},
                    '175': {'descriptor': 'TEMP SLOT 057', 'status': 'OK, Swapped', 'value': '37C', 'value_raw': 285227264},
                    '176': {'descriptor': 'TEMP SLOT 058', 'status': 'OK, Swapped', 'value': '36C', 'value_raw': 285227008},
                    '177': {'descriptor': 'TEMP SLOT 059', 'status': 'OK, Swapped', 'value': '33C', 'value_raw': 285226240},
                    '178': {'descriptor': 'TEMP SLOT 060', 'status': 'OK, Swapped', 'value': '32C', 'value_raw': 285225984},
                    '179': {'descriptor': 'TEMP SLOT 061', 'status': 'OK, Swapped', 'value': '35C', 'value_raw': 285226752},
                    '180': {'descriptor': 'TEMP SLOT 062', 'status': 'OK, Swapped', 'value': '37C', 'value_raw': 285227264},
                    '181': {'descriptor': 'TEMP SLOT 063', 'status': 'OK, Swapped', 'value': '37C', 'value_raw': 285227264},
                    '182': {'descriptor': 'TEMP SLOT 064', 'status': 'OK, Swapped', 'value': '38C', 'value_raw': 285227520},
                    '183': {'descriptor': 'TEMP SLOT 065', 'status': 'OK, Swapped', 'value': '38C', 'value_raw': 285227520},
                    '184': {'descriptor': 'TEMP SLOT 066', 'status': 'OK, Swapped', 'value': '41C', 'value_raw': 285228288},
                    '185': {'descriptor': 'TEMP SLOT 067', 'status': 'OK, Swapped', 'value': '43C', 'value_raw': 285228800},
                    '186': {'descriptor': 'TEMP SLOT 068', 'status': 'OK, Swapped', 'value': '43C', 'value_raw': 285228800},
                    '187': {'descriptor': 'TEMP SLOT 069', 'status': 'OK, Swapped', 'value': '44C', 'value_raw': 285229056},
                    '188': {'descriptor': 'TEMP SLOT 070', 'status': 'OK, Swapped', 'value': '43C', 'value_raw': 285228800},
                    '189': {'descriptor': 'TEMP SLOT 071', 'status': 'OK, Swapped', 'value': '41C', 'value_raw': 285228288},
                    '190': {'descriptor': 'TEMP SLOT 072', 'status': 'OK, Swapped', 'value': '39C', 'value_raw': 285227776},
                    '191': {'descriptor': 'TEMP SLOT 073', 'status': 'OK, Swapped', 'value': '42C', 'value_raw': 285228544},
                    '192': {'descriptor': 'TEMP SLOT 074', 'status': 'OK, Swapped', 'value': '44C', 'value_raw': 285229056},
                    '193': {'descriptor': 'TEMP SLOT 075', 'status': 'OK, Swapped', 'value': '44C', 'value_raw': 285229056},
                    '194': {'descriptor': 'TEMP SLOT 076', 'status': 'OK, Swapped', 'value': '44C', 'value_raw': 285229056},
                    '195': {'descriptor': 'TEMP SLOT 077', 'status': 'OK, Swapped', 'value': '43C', 'value_raw': 285228800}, 
                    '196': {'descriptor': 'TEMP SLOT 078', 'status': 'OK, Swapped', 'value': '44C', 'value_raw': 285229056},
                    '197': {'descriptor': 'TEMP SLOT 079', 'status': 'OK, Swapped', 'value': '46C', 'value_raw': 285229568},
                    '198': {'descriptor': 'TEMP SLOT 080', 'status': 'OK, Swapped', 'value': '48C', 'value_raw': 285230080},
                    '199': {'descriptor': 'TEMP SLOT 081', 'status': 'OK, Swapped', 'value': '48C', 'value_raw': 285230080},
                    '200': {'descriptor': 'TEMP SLOT 082', 'status': 'OK, Swapped', 'value': '48C', 'value_raw': 285230080},
                    '201': {'descriptor': 'TEMP SLOT 083', 'status': 'OK, Swapped', 'value': '46C', 'value_raw': 285229568},
                    '202': {'descriptor': 'TEMP SLOT 084', 'status': 'OK, Swapped', 'value': '44C', 'value_raw': 285229056},
                    '203': {'descriptor': 'TEMP SLOT 085', 'status': 'OK, Swapped', 'value': '47C', 'value_raw': 285229824},
                    '204': {'descriptor': 'TEMP SLOT 086', 'status': 'OK, Swapped', 'value': '48C', 'value_raw': 285230080},
                    '205': {'descriptor': 'TEMP SLOT 087', 'status': 'OK', 'value': '48C', 'value_raw': 16794624},
                    '206': {'descriptor': 'TEMP SLOT 088', 'status': 'OK, Swapped', 'value': '48C', 'value_raw': 285230080},
                    '207': {'descriptor': 'TEMP SLOT 089', 'status': 'OK, Swapped', 'value': '45C', 'value_raw': 285229312},
                    '208': {'descriptor': 'TEMP SLOT 090', 'status': 'OK, Swapped', 'value': '43C', 'value_raw': 285228800},
                    '209': {'descriptor': 'TEMP SLOT 091', 'status': 'OK, Swapped', 'value': '46C', 'value_raw': 285229568},
                    '210': {'descriptor': 'TEMP SLOT 092', 'status': 'OK, Swapped', 'value': '47C', 'value_raw': 285229824},
                    '211': {'descriptor': 'TEMP SLOT 093', 'status': 'OK, Swapped', 'value': '48C', 'value_raw': 285230080},
                    '212': {'descriptor': 'TEMP SLOT 094', 'status': 'OK, Swapped', 'value': '48C', 'value_raw': 285230080},
                    '213': {'descriptor': 'TEMP SLOT 095', 'status': 'OK, Swapped', 'value': '46C', 'value_raw': 285229568},
                    '214': {'descriptor': 'TEMP SLOT 096', 'status': 'OK, Swapped', 'value': '43C', 'value_raw': 285228800},
                    '215': {'descriptor': 'TEMP SLOT 097', 'status': 'OK, Swapped', 'value': '46C', 'value_raw': 285229568},
                    '216': {'descriptor': 'TEMP SLOT 098', 'status': 'OK, Swapped', 'value': '48C', 'value_raw': 285230080},
                    '217': {'descriptor': 'TEMP SLOT 099', 'status': 'OK, Swapped', 'value': '48C', 'value_raw': 285230080},
                    '218': {'descriptor': 'TEMP SLOT 100', 'status': 'OK, Swapped', 'value': '47C', 'value_raw': 285229824},
                    '219': {'descriptor': 'TEMP SLOT 101', 'status': 'OK, Swapped', 'value': '44C', 'value_raw': 285229056},
                    '220': {'descriptor': 'TEMP IOM A', 'status': 'OK', 'value': '49C', 'value_raw': 16794880},
                    '221': {'descriptor': 'TEMP IOM B', 'status': 'OK', 'value': '52C', 'value_raw': 16795648},
                    '222': {'descriptor': 'TEMP BB 60 1', 'status': 'OK', 'value': '28C', 'value_raw': 16789504},
                    '223': {'descriptor': 'TEMP BB 60 2', 'status': 'OK', 'value': '31C', 'value_raw': 16790272},
                    '224': {'descriptor': 'TEMP BB 42 1', 'status': 'OK', 'value': '18C', 'value_raw': 16786944},
                    '225': {'descriptor': 'TEMP BB 42 2', 'status': 'OK', 'value': '18C', 'value_raw': 16786944},
                    '226': {'descriptor': 'TEMP PRI A DIE', 'status': 'OK', 'value': '59C', 'value_raw': 16797440},
                    '227': {'descriptor': 'TEMP SEC1 A DIE', 'status': 'OK', 'value': '75C', 'value_raw': 16801536},
                    '228': {'descriptor': 'TEMP SEC2 A DIE', 'status': 'OK', 'value': '61C', 'value_raw': 16797952},
                    '229': {'descriptor': 'TEMP PRI A MEM', 'status': 'OK', 'value': '46C', 'value_raw': 16794112},
                    '230': {'descriptor': 'TEMP SEC1 A MEM', 'status': 'OK', 'value': '45C', 'value_raw': 16793856},
                    '231': {'descriptor': 'TEMP SEC2 A MEM', 'status': 'OK', 'value': '38C', 'value_raw': 16792064},
                    '232': {'descriptor': 'TEMP PRI B DIE', 'status': 'OK', 'value': '59C', 'value_raw': 16797440},
                    '233': {'descriptor': 'TEMP SEC1 B DIE', 'status': 'OK', 'value': '79C', 'value_raw': 16802560},
                    '234': {'descriptor': 'TEMP SEC2 B DIE', 'status': 'OK', 'value': '67C', 'value_raw': 16799488},
                    '235': {'descriptor': 'TEMP PRI B MEM', 'status': 'OK', 'value': '49C', 'value_raw': 16794880},
                    '236': {'descriptor': 'TEMP SEC1 B MEM', 'status': 'OK', 'value': '49C', 'value_raw': 16794880},
                    '237': {'descriptor': 'TEMP SEC2 B MEM', 'status': 'OK', 'value': '40C', 'value_raw': 16792576},
                    '238': {'descriptor': 'TEMP IOM A 5V', 'status': 'OK', 'value': '51C', 'value_raw': 16795392},
                    '239': {'descriptor': 'TEMP IOM B 5V', 'status': 'OK', 'value': '45C', 'value_raw': 16793856},
                    '240': {'descriptor': 'TEMP PSU A AMB', 'status': 'OK', 'value': '36C', 'value_raw': 16791552},
                    '241': {'descriptor': 'TEMP PSU A HOT', 'status': 'OK', 'value': '49C', 'value_raw': 16794880},
                    '242': {'descriptor': 'TEMP PSU A PRI', 'status': 'OK', 'value': '43C', 'value_raw': 16793344},
                    '243': {'descriptor': 'TEMP PSU B AMB', 'status': 'OK', 'value': '34C', 'value_raw': 16791040},
                    '244': {'descriptor': 'TEMP PSU B HOT', 'status': 'OK', 'value': '48C', 'value_raw': 16794624},
                    '245': {'descriptor': 'TEMP PSU B PRI', 'status': 'OK', 'value': '42C', 'value_raw': 16793088}
                },
                'Enclosure Services Controller Electronics': {
                    '247': {'descriptor': 'ESCE IOMA,1EA0484-C1          ,THCCT03821EG00F9    ,5000CCAB051140BC,,00:0C:CA:07:44:54,3.1.11', 'status': 'OK', 'value': None, 'value_raw': 17826176},
                    '248': {'descriptor': 'ESCE IOMB,1EA0484-C1          ,THCCT03821EG00FA    ,5000CCAB051140FC,,00:0C:CA:07:44:55,3.1.11', 'status': 'OK', 'value': None, 'value_raw': 17825920}
                },
                'SAS Expander': {
                    '250': {'descriptor': 'EXP IOMA 0,3010-007,5000CCAB051140BD', 'status': 'OK', 'value': None, 'value_raw': 16777216},
                    '251': {'descriptor': 'EXP IOMA 1,3010-007,5000CCAB051140BF', 'status': 'OK', 'value': None, 'value_raw': 16777216},
                    '252': {'descriptor': 'EXP IOMA 2,3010-007,5000CCAB051140FF', 'status': 'OK', 'value': None, 'value_raw': 16777216},
                    '253': {'descriptor': 'EXP IOMB 0,3010-007,5000CCAB051140FD', 'status': 'OK', 'value': None, 'value_raw': 16777216},
                    '254': {'descriptor': 'EXP IOMB 1,3010-007,5000CCAB051140F9', 'status': 'OK', 'value': None, 'value_raw': 16777216},
                    '255': {'descriptor': 'EXP IOMB 2,3010-007,5000CCAB051140FB', 'status': 'OK', 'value': None, 'value_raw': 16777216}
                },
                'SAS Connector': {
                    '257': {'descriptor': 'CONN HOST 00', 'status': 'OK', 'value': 'Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]', 'value_raw': 17170304},
                    '258': {'descriptor': 'CONN HOST 01', 'status': 'Not installed', 'value': 'Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]', 'value_raw': 84279040},
                    '259': {'descriptor': 'CONN HOST 02', 'status': 'Not installed', 'value': 'Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]', 'value_raw': 84279040},
                    '260': {'descriptor': 'CONN HOST 03', 'status': 'Not installed', 'value': 'Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]', 'value_raw': 84279040},
                    '261': {'descriptor': 'CONN HOST 04', 'status': 'Not installed', 'value': 'Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]', 'value_raw': 84279040},
                    '262': {'descriptor': 'CONN HOST 05', 'status': 'Not installed', 'value': 'Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]', 'value_raw': 84279040},
                    '263': {'descriptor': 'CONN HOST 06', 'status': 'OK', 'value': 'Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]', 'value_raw': 17170304},
                    '264': {'descriptor': 'CONN HOST 07', 'status': 'Not installed', 'value': 'Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]', 'value_raw': 84279040},
                    '265': {'descriptor': 'CONN HOST 08', 'status': 'Not installed', 'value': 'Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]', 'value_raw': 84279040},
                    '266': {'descriptor': 'CONN HOST 09', 'status': 'Not installed', 'value': 'Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]', 'value_raw': 84279040},
                    '267': {'descriptor': 'CONN HOST 10', 'status': 'Not installed', 'value': 'Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]', 'value_raw': 84279040},
                    '268': {'descriptor': 'CONN HOST 11', 'status': 'Not installed', 'value': 'Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]', 'value_raw': 84279040}
                },
                'Voltage Sensor': {
                    '270': {'descriptor': 'VOLT PSU A AC', 'status': 'OK', 'value': '200.0V', 'value_raw': 16797216},
                    '271': {'descriptor': 'VOLT PSU A 12V', 'status': 'OK', 'value': '12.29V', 'value_raw': 16778445},
                    '272': {'descriptor': 'VOLT PSU B AC', 'status': 'OK', 'value': '202.0V', 'value_raw': 16797416},
                    '273': {'descriptor': 'VOLT PSU B 12V', 'status': 'OK', 'value': '12.23V', 'value_raw': 16778439},
                    '274': {'descriptor': 'VOLT IOM A 5V', 'status': 'OK', 'value': '5.03V', 'value_raw': 16777719},
                    '275': {'descriptor': 'VOLT IOM A 12V', 'status': 'OK', 'value': '12.0V', 'value_raw': 16778416},
                    '276': {'descriptor': 'VOLT IOM B 5V', 'status': 'OK', 'value': '5.03V', 'value_raw': 16777719},
                    '277': {'descriptor': 'VOLT IOM B 12V', 'status': 'OK', 'value': '12.0V', 'value_raw': 16778416}
                },
                'Current Sensor': {
                    '279': {'descriptor': 'CURR PSU A IN', 'status': 'OK', 'value': '2.16A', 'value_raw': 16777432},
                    '280': {'descriptor': 'CURR PSU A OUT', 'status': 'OK', 'value': '32.31A', 'value_raw': 16780447},
                    '281': {'descriptor': 'CURR PSU B IN', 'status': 'OK', 'value': '2.16A', 'value_raw': 16777432},
                    '282': {'descriptor': 'CURR PSU B OUT', 'status': 'OK', 'value': '32.81A', 'value_raw': 16780497},
                    '283': {'descriptor': 'CURR IOM A 12V', 'status': 'OK', 'value': '15.54A', 'value_raw': 16778770},
                    '284': {'descriptor': 'CURR IOM A 5V', 'status': 'OK', 'value': '23.75A', 'value_raw': 16779591},
                    '285': {'descriptor': 'CURR IOM B 12V', 'status': 'OK', 'value': '13.3A', 'value_raw': 16778546},
                    '286': {'descriptor': 'CURR IOM B 5V', 'status': 'OK', 'value': '20.0A', 'value_raw': 16779216}
                },
                'Door Lock': {
                    '288': {'descriptor': 'ENCLOSURE COVER', 'status': 'OK', 'value': None, 'value_raw': 16777216}
                }
            },
            'label': 'HGST H4102-J 3010'
        },
        {  # for mocking sysfs directory structure
            11: 'sdlc', 78: 'sdac', 52: 'sdnc', 101: 'sddu', 77: 'sdu', 2: 'sdkp', 79: 'sdz', 40: 'sdmp', 29: 'sdma', 42: 'sdb',
            10: 'sdky', 8: 'sdla', 0: 'sdkn', 41: 'sdmq', 93: 'sdby', 88: 'sdbq', 63: 'sdk', 45: 'sdmt', 3: 'sdkq', 46: 'sdmu',
            68: 'sdad', 25: 'sdlu', 75: 'sdr', 31: 'sdmf', 60: 'sdi', 65: 'sdm', 9: 'sdkv', 85: 'sdbm', 90: 'sdbx', 5: 'sdkt',
            72: 'sdt', 83: 'sdbl', 62: 'sdn', 56: 'sda', 35: 'sdmi', 81: 'sdab', 53: 'sde', 51: 'sdnb', 32: 'sdme', 57: 'sdc',
            98: 'sdcd', 96: 'sdcc', 58: 'sdd', 19: 'sdll', 86: 'sdcn', 59: 'sdl', 14: 'sdlf', 97: 'sdci', 37: 'sdml', 76: 'sdx',
            28: 'sdlz', 43: 'sdmr', 47: 'sdmv', 38: 'sdmm', 73: 'sdq', 55: 'sdh', 4: 'sdks', 89: 'sdbr', 22: 'sdlq', 24: 'sdls',
            6: 'sdku', 36: 'sdmk', 82: 'sdaf', 1: 'sdko', 12: 'sdld', 66: 'sdae', 67: 'sds', 15: 'sdlh', 23: 'sdlr', 74: 'sdw',
            50: 'sdna', 87: 'sdbo', 69: 'sdv', 71: 'sdp', 21: 'sdlo', 13: 'sdle', 20: 'sdln', 30: 'sdmb', 91: 'sdbz', 39: 'sdmo',
            18: 'sdlm', 7: 'sdkw', 44: 'sdg', 17: 'sdlj', 70: 'sdy', 34: 'sdmg', 49: 'sdmz', 16: 'sdlg', 84: 'sdbn', 92: 'sdbt',
            26: 'sdlv', 100: 'sdda', 54: 'sdf', 61: 'sdj', 33: 'sdmh', 27: 'sdlw', 95: 'sddy', 80: 'sdaa', 64: 'sdo', 99: 'sdck',
            48: 'sdmx', 94: 'sdcb'
        }
    )
])
def test_enclosure_class(data):
    raw, formatted, sysfs_disks = data
    with patch('middlewared.utils.scsi_generic.inquiry') as inquiry:
        inquiry.return_value = {
            'vendor': formatted['vendor'],
            'product': formatted['product'],
            'revision': formatted['revision'],
        }
        with patch('middlewared.plugins.enclosure_.sysfs_disks.map_disks_to_enclosure_slots') as map_disks_to_enclosure_slots:
            map_disks_to_enclosure_slots.return_value = sysfs_disks

            enc = Enclosure(
                formatted['bsg'],
                formatted['sg'],
                formatted['dmi'],
                raw,
            )
            assert enc.asdict() == formatted
