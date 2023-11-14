from unittest.mock import patch

import pytest

from middlewared.plugins.enclosure_.enclosure_class import Enclosure


@pytest.mark.parametrize('data', [
    (
        {  # H10 head-unit libsg3.ses.EnclosureDevice.status() output
            "id": "3b0ad6d1c00007c0",
            "name": "BROADCOMVirtualSES03",
            "status": [
                "OK"
            ],
            "elements": {
                "0": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        0,
                        0,
                        0,
                        0
                    ]
                },
                "1": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        5,
                        0,
                        0,
                        0
                    ]
                },
                "2": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        5,
                        0,
                        0,
                        0
                    ]
                },
                "3": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "4": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        5,
                        0,
                        0,
                        0
                    ]
                },
                "5": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        0,
                        0,
                        0,
                        0
                    ]
                },
                "6": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        0,
                        0,
                        0,
                        0
                    ]
                },
                "7": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        0,
                        0,
                        0,
                        0
                    ]
                },
                "8": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        0,
                        0,
                        0,
                        0
                    ]
                },
                "9": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        5,
                        0,
                        0,
                        0
                    ]
                },
                "10": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        5,
                        0,
                        0,
                        0
                    ]
                },
                "11": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        5,
                        0,
                        0,
                        0
                    ]
                },
                "12": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        5,
                        0,
                        0,
                        0
                    ]
                },
                "13": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        5,
                        0,
                        0,
                        0
                    ]
                },
                "14": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "15": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "16": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "17": {
                    "type": 25,
                    "descriptor": "<empty>",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "18": {
                    "type": 25,
                    "descriptor": "C1.0",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "19": {
                    "type": 25,
                    "descriptor": "C1.0",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "20": {
                    "type": 25,
                    "descriptor": "C1.0",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "21": {
                    "type": 25,
                    "descriptor": "C1.0",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "22": {
                    "type": 25,
                    "descriptor": "<empty>",
                    "status": [
                        5,
                        0,
                        0,
                        0
                    ]
                },
                "23": {
                    "type": 25,
                    "descriptor": "<empty>",
                    "status": [
                        5,
                        0,
                        0,
                        0
                    ]
                },
                "24": {
                    "type": 25,
                    "descriptor": "<empty>",
                    "status": [
                        5,
                        0,
                        0,
                        0
                    ]
                },
                "25": {
                    "type": 25,
                    "descriptor": "<empty>",
                    "status": [
                        5,
                        0,
                        0,
                        0
                    ]
                },
                "26": {
                    "type": 25,
                    "descriptor": "C1.1",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "27": {
                    "type": 25,
                    "descriptor": "C1.1",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "28": {
                    "type": 25,
                    "descriptor": "C1.1",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "29": {
                    "type": 25,
                    "descriptor": "C1.1",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "30": {
                    "type": 25,
                    "descriptor": "C1.2",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "31": {
                    "type": 25,
                    "descriptor": "C1.2",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "32": {
                    "type": 25,
                    "descriptor": "C1.2",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "33": {
                    "type": 25,
                    "descriptor": "C1.2",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                }
            }
        },
        {  # H10 head-unit expected enclosure_class.py::Enclosure().asdict() output
            "name": "BROADCOM VirtualSES 03",
            "model": "H10",
            "controller": True,
            "dmi": "TRUENAS-H10-HA",
            "status": [
                "OK"
            ],
            "id": "3b0ad6d1c00007c0",
            "vendor": "BROADCOM",
            "product": "VirtualSES",
            "revision": "03",
            "bsg": "/dev/bsg/0:0:0:0",
            "sg": "/dev/sg1",
            "pci": "0:0:0:0",
            "elements": {
                "Array Device Slot": {
                    "9": {
                        "descriptor": "<empty>",
                        "status": "Not installed",
                        "value": None,
                        "value_raw": 83886080,
                        "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0",
                            "enclosure_sg": "/dev/sg1",
                            "enclosure_bsg": "/dev/bsg/0:0:0:0",
                            "descriptor": "slot1",
                            "slot": 1
                        }
                    },
                    "10": {
                        "descriptor": "<empty>",
                        "status": "Not installed",
                        "value": None,
                        "value_raw": 83886080,
                        "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0",
                            "enclosure_sg": "/dev/sg1",
                            "enclosure_bsg": "/dev/bsg/0:0:0:0",
                            "descriptor": "slot2",
                            "slot": 2
                        }
                    },
                    "11": {
                        "descriptor": "<empty>",
                        "status": "OK",
                        "value": None,
                        "value_raw": 16777216,
                        "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0",
                            "enclosure_sg": "/dev/sg1",
                            "enclosure_bsg": "/dev/bsg/0:0:0:0",
                            "descriptor": "slot3",
                            "slot": 3
                        }
                    },
                    "12": {
                        "descriptor": "<empty>",
                        "status": "Not installed",
                        "value": None,
                        "value_raw": 83886080,
                        "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0",
                            "enclosure_sg": "/dev/sg1",
                            "enclosure_bsg": "/dev/bsg/0:0:0:0",
                            "descriptor": "slot4",
                            "slot": 4
                        }
                    },
                    "1": {
                        "descriptor": "<empty>",
                        "status": "Not installed",
                        "value": None,
                        "value_raw": 83886080,
                        "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0",
                            "enclosure_sg": "/dev/sg1",
                            "enclosure_bsg": "/dev/bsg/0:0:0:0",
                            "descriptor": "slot9",
                            "slot": 9
                        }
                    },
                    "2": {
                        "descriptor": "<empty>",
                        "status": "Not installed",
                        "value": None,
                        "value_raw": 83886080,
                        "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0",
                            "enclosure_sg": "/dev/sg1",
                            "enclosure_bsg": "/dev/bsg/0:0:0:0",
                            "descriptor": "slot10",
                            "slot": 10
                        }
                    },
                    "3": {
                        "descriptor": "<empty>",
                        "status": "Not installed",
                        "value": None,
                        "value_raw": 83886080,
                        "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0",
                            "enclosure_sg": "/dev/sg1",
                            "enclosure_bsg": "/dev/bsg/0:0:0:0",
                            "descriptor": "slot11",
                            "slot": 11
                        }
                    },
                    "4": {
                        "descriptor": "<empty>",
                        "status": "Not installed",
                        "value": None,
                        "value_raw": 83886080,
                        "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0",
                            "enclosure_sg": "/dev/sg1",
                            "enclosure_bsg": "/dev/bsg/0:0:0:0",
                            "descriptor": "slot12",
                            "slot": 12
                        }
                    },
                    "5": {
                        "descriptor": "<empty>",
                        "status": "Not installed",
                        "value": None,
                        "value_raw": 83886080,
                        "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0",
                            "enclosure_sg": "/dev/sg1",
                            "enclosure_bsg": "/dev/bsg/0:0:0:0",
                            "descriptor": "slot13",
                            "slot": 13
                        }
                    },
                    "6": {
                        "descriptor": "<empty>",
                        "status": "OK",
                        "value": None,
                        "value_raw": 16777216,
                        "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0",
                            "enclosure_sg": "/dev/sg1",
                            "enclosure_bsg": "/dev/bsg/0:0:0:0",
                            "descriptor": "slot14",
                            "slot": 14
                        }
                    },
                    "7": {
                        "descriptor": "<empty>",
                        "status": "OK",
                        "value": None,
                        "value_raw": 16777216,
                        "dev": None,
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0",
                            "enclosure_sg": "/dev/sg1",
                            "enclosure_bsg": "/dev/bsg/0:0:0:0",
                            "descriptor": "slot15",
                            "slot": 15
                        }
                    },
                    "8": {
                        "descriptor": "<empty>",
                        "status": "OK",
                        "value": None,
                        "value_raw": 16777216,
                        "dev": "sda",
                        "original": {
                            "enclosure_id": "3b0ad6d1c00007c0",
                            "enclosure_sg": "/dev/sg1",
                            "enclosure_bsg": "/dev/bsg/0:0:0:0",
                            "descriptor": "slot16",
                            "slot": 16
                        }
                    }
                },
                "SAS Connector": {
                    "17": {
                        "descriptor": "<empty>",
                        "status": "OK",
                        "value": "No information",
                        "value_raw": 16777216
                    },
                    "18": {
                        "descriptor": "C1.0",
                        "status": "OK",
                        "value": "No information",
                        "value_raw": 16777216
                    },
                    "19": {
                        "descriptor": "C1.0",
                        "status": "OK",
                        "value": "No information",
                        "value_raw": 16777216
                    },
                    "20": {
                        "descriptor": "C1.0",
                        "status": "OK",
                        "value": "No information",
                        "value_raw": 16777216
                    },
                    "21": {
                        "descriptor": "C1.0",
                        "status": "OK",
                        "value": "No information",
                        "value_raw": 16777216
                    },
                    "22": {
                        "descriptor": "<empty>",
                        "status": "Not installed",
                        "value": "No information",
                        "value_raw": 83886080
                    },
                    "23": {
                        "descriptor": "<empty>",
                        "status": "Not installed",
                        "value": "No information",
                        "value_raw": 83886080
                    },
                    "24": {
                        "descriptor": "<empty>",
                        "status": "Not installed",
                        "value": "No information",
                        "value_raw": 83886080
                    },
                    "25": {
                        "descriptor": "<empty>",
                        "status": "Not installed",
                        "value": "No information",
                        "value_raw": 83886080
                    },
                    "26": {
                        "descriptor": "C1.1",
                        "status": "OK",
                        "value": "No information",
                        "value_raw": 16777216
                    },
                    "27": {
                        "descriptor": "C1.1",
                        "status": "OK",
                        "value": "No information",
                        "value_raw": 16777216
                    },
                    "28": {
                        "descriptor": "C1.1",
                        "status": "OK",
                        "value": "No information",
                        "value_raw": 16777216
                    },
                    "29": {
                        "descriptor": "C1.1",
                        "status": "OK",
                        "value": "No information",
                        "value_raw": 16777216
                    },
                    "30": {
                        "descriptor": "C1.2",
                        "status": "OK",
                        "value": "No information",
                        "value_raw": 16777216
                    },
                    "31": {
                        "descriptor": "C1.2",
                        "status": "OK",
                        "value": "No information",
                        "value_raw": 16777216
                    },
                    "32": {
                        "descriptor": "C1.2",
                        "status": "OK",
                        "value": "No information",
                        "value_raw": 16777216
                    },
                    "33": {
                        "descriptor": "C1.2",
                        "status": "OK",
                        "value": "No information",
                        "value_raw": 16777216
                    }
                }
            }
        },
        {  # H10 head-unit sysfs output (for mocking)
            "7": "sda",
            "5": None,
            "11": None,
            "3": None,
            "9": None,
            "0": None,
            "6": None,
            "4": None,
            "10": None,
            "2": None,
            "8": None,
            "1": None
        }
    ),
    (
        {  # ES102 JBOD libsg3.ses.EnclosureDevice.status() output
            "id": "5000ccab05116800",
            "name": "HGSTH4102-J3010",
            "status": [
                "INFO"
            ],
            "elements": {
                "0": {
                    "type": 23,
                    "descriptor": "<empty>",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "1": {
                    "type": 23,
                    "descriptor": "SLOT 000,3FG1KMYV           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "2": {
                    "type": 23,
                    "descriptor": "SLOT 001,3FJ3J58T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "3": {
                    "type": 23,
                    "descriptor": "SLOT 002,3FHXK2YT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "4": {
                    "type": 23,
                    "descriptor": "SLOT 003,3FJG59GT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "5": {
                    "type": 23,
                    "descriptor": "SLOT 004,3FJ1S32T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "6": {
                    "type": 23,
                    "descriptor": "SLOT 005,3FJJ76GT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "7": {
                    "type": 23,
                    "descriptor": "SLOT 006,3FHXGM8T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "8": {
                    "type": 23,
                    "descriptor": "SLOT 007,3FG1KLKV           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "9": {
                    "type": 23,
                    "descriptor": "SLOT 008,3FJ2NY8T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "10": {
                    "type": 23,
                    "descriptor": "SLOT 009,3FJ2LYPT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "11": {
                    "type": 23,
                    "descriptor": "SLOT 010,3FJJZZ4T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "12": {
                    "type": 23,
                    "descriptor": "SLOT 011,3FH53S0T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "13": {
                    "type": 23,
                    "descriptor": "SLOT 012,3FJJ187T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "14": {
                    "type": 23,
                    "descriptor": "SLOT 013,3FJ0DURT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "15": {
                    "type": 23,
                    "descriptor": "SLOT 014,3FJ30KNT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "16": {
                    "type": 23,
                    "descriptor": "SLOT 015,3FJK5B3T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "17": {
                    "type": 23,
                    "descriptor": "SLOT 016,3FG3RGDV           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "18": {
                    "type": 23,
                    "descriptor": "SLOT 017,3FJ28KNT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "19": {
                    "type": 23,
                    "descriptor": "SLOT 018,3FH3Z5PT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "20": {
                    "type": 23,
                    "descriptor": "SLOT 019,3FJ33PZT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "21": {
                    "type": 23,
                    "descriptor": "SLOT 020,3FJ1M3AT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "22": {
                    "type": 23,
                    "descriptor": "SLOT 021,3FJ2WG5T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "23": {
                    "type": 23,
                    "descriptor": "SLOT 022,3FJK5M6T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "24": {
                    "type": 23,
                    "descriptor": "SLOT 023,3FJ2H8YT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "25": {
                    "type": 23,
                    "descriptor": "SLOT 024,3FHZRBXT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "26": {
                    "type": 23,
                    "descriptor": "SLOT 025,3RHSMW3A           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "27": {
                    "type": 23,
                    "descriptor": "SLOT 026,3FJ1U45T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "28": {
                    "type": 23,
                    "descriptor": "SLOT 027,3FHLT9RT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "29": {
                    "type": 23,
                    "descriptor": "SLOT 028,3FJ2LMDT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "30": {
                    "type": 23,
                    "descriptor": "SLOT 029,3FJ28Y8T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "31": {
                    "type": 23,
                    "descriptor": "SLOT 030,3FH4VDMT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "32": {
                    "type": 23,
                    "descriptor": "SLOT 031,3FJ2A3TT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "33": {
                    "type": 23,
                    "descriptor": "SLOT 032,3FHR3PJT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "34": {
                    "type": 23,
                    "descriptor": "SLOT 033,3FHP4AVT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "35": {
                    "type": 23,
                    "descriptor": "SLOT 034,3FJ2G3YT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "36": {
                    "type": 23,
                    "descriptor": "SLOT 035,3FHLKBRT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "37": {
                    "type": 23,
                    "descriptor": "SLOT 036,3FHY7VST           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "38": {
                    "type": 23,
                    "descriptor": "SLOT 037,3FHYE9YT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "39": {
                    "type": 23,
                    "descriptor": "SLOT 038,3FH4UY6T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "40": {
                    "type": 23,
                    "descriptor": "SLOT 039,3FHMJ0DT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "41": {
                    "type": 23,
                    "descriptor": "SLOT 040,3FJ2P79T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "42": {
                    "type": 23,
                    "descriptor": "SLOT 041,3FHZRBZT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "43": {
                    "type": 23,
                    "descriptor": "SLOT 042,3FHYGT9T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "44": {
                    "type": 23,
                    "descriptor": "SLOT 043,3FJJZZ7T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "45": {
                    "type": 23,
                    "descriptor": "SLOT 044,3FJ2MSXT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "46": {
                    "type": 23,
                    "descriptor": "SLOT 045,3FG1KKPV           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "47": {
                    "type": 23,
                    "descriptor": "SLOT 046,3FHYYKGT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "48": {
                    "type": 23,
                    "descriptor": "SLOT 047,3FHXGWZT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "49": {
                    "type": 23,
                    "descriptor": "SLOT 048,3FJ2Z5LT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "50": {
                    "type": 23,
                    "descriptor": "SLOT 049,3FJ1781T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "51": {
                    "type": 23,
                    "descriptor": "SLOT 050,3FH83XZT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "52": {
                    "type": 23,
                    "descriptor": "SLOT 051,3RHLZ4RA           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "53": {
                    "type": 23,
                    "descriptor": "SLOT 052,3FJ2WPAT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "54": {
                    "type": 23,
                    "descriptor": "SLOT 053,3FJ1411T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "55": {
                    "type": 23,
                    "descriptor": "SLOT 054,3FG3RB8V           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "56": {
                    "type": 23,
                    "descriptor": "SLOT 055,3FJ2KNDT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "57": {
                    "type": 23,
                    "descriptor": "SLOT 056,3FHP6BPT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "58": {
                    "type": 23,
                    "descriptor": "SLOT 057,3FHDKGTT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "59": {
                    "type": 23,
                    "descriptor": "SLOT 058,3FJ2W4UT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "60": {
                    "type": 23,
                    "descriptor": "SLOT 059,3FJ1441T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "61": {
                    "type": 23,
                    "descriptor": "SLOT 060,3FJ2S29T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "62": {
                    "type": 23,
                    "descriptor": "SLOT 061,3FHY77PT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "63": {
                    "type": 23,
                    "descriptor": "SLOT 062,3FHPWTJT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "64": {
                    "type": 23,
                    "descriptor": "SLOT 063,3FJ2S2VT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "65": {
                    "type": 23,
                    "descriptor": "SLOT 064,3FH260RT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "66": {
                    "type": 23,
                    "descriptor": "SLOT 065,3FHP66DT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "67": {
                    "type": 23,
                    "descriptor": "SLOT 066,3FHPYD1T           ",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "68": {
                    "type": 23,
                    "descriptor": "SLOT 067,3FJ2MW6T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "69": {
                    "type": 23,
                    "descriptor": "SLOT 068,3FJ29WNT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "70": {
                    "type": 23,
                    "descriptor": "SLOT 069,3FJ2S30T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "71": {
                    "type": 23,
                    "descriptor": "SLOT 070,3FJ1V6PT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "72": {
                    "type": 23,
                    "descriptor": "SLOT 071,3FJ1WEWT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "73": {
                    "type": 23,
                    "descriptor": "SLOT 072,3FJ15PGT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "74": {
                    "type": 23,
                    "descriptor": "SLOT 073,3FJJX6DT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "75": {
                    "type": 23,
                    "descriptor": "SLOT 074,3FJ309HT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "76": {
                    "type": 23,
                    "descriptor": "SLOT 075,3FJ2H29T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "77": {
                    "type": 23,
                    "descriptor": "SLOT 076,3FJ1433T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "78": {
                    "type": 23,
                    "descriptor": "SLOT 077,3FJ2KL9T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "79": {
                    "type": 23,
                    "descriptor": "SLOT 078,3FJ19DTT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "80": {
                    "type": 23,
                    "descriptor": "SLOT 079,3FJ2P37T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "81": {
                    "type": 23,
                    "descriptor": "SLOT 080,3FHYY0ZT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "82": {
                    "type": 23,
                    "descriptor": "SLOT 081,3FHN8LKT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "83": {
                    "type": 23,
                    "descriptor": "SLOT 082,3FJ1J3GT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "84": {
                    "type": 23,
                    "descriptor": "SLOT 083,3FHYLP7T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "85": {
                    "type": 23,
                    "descriptor": "SLOT 084,3FJ15SRT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "86": {
                    "type": 23,
                    "descriptor": "SLOT 085,3FHKW9GT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "87": {
                    "type": 23,
                    "descriptor": "SLOT 086,3FHYEVJT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "88": {
                    "type": 23,
                    "descriptor": "SLOT 087,3FJ2A5VT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "89": {
                    "type": 23,
                    "descriptor": "SLOT 088,3FJ2MU9T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "90": {
                    "type": 23,
                    "descriptor": "SLOT 089,3FJ197HT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "91": {
                    "type": 23,
                    "descriptor": "SLOT 090,3FJ29S7T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "92": {
                    "type": 23,
                    "descriptor": "SLOT 091,3FJ2P7DT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "93": {
                    "type": 23,
                    "descriptor": "SLOT 092,3FHY8KTT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "94": {
                    "type": 23,
                    "descriptor": "SLOT 093,3FHY81RT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "95": {
                    "type": 23,
                    "descriptor": "SLOT 094,3FJ153KT           ",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "96": {
                    "type": 23,
                    "descriptor": "SLOT 095,3FJ17XBT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "97": {
                    "type": 23,
                    "descriptor": "SLOT 096,3FJ3J3ST           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "98": {
                    "type": 23,
                    "descriptor": "SLOT 097,3FJ2MU0T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "99": {
                    "type": 23,
                    "descriptor": "SLOT 098,3FJ2A7LT           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "100": {
                    "type": 23,
                    "descriptor": "SLOT 099,3FJ29V3T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "101": {
                    "type": 23,
                    "descriptor": "SLOT 100,3FHYW3ST           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "102": {
                    "type": 23,
                    "descriptor": "SLOT 101,3FJ2S36T           ",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "103": {
                    "type": 14,
                    "descriptor": "<empty>",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "104": {
                    "type": 14,
                    "descriptor": "ENCLOSURE,1ES1846-A3,THCCT03921EA0015,1EB1173-A1,THCCT03721EJ1945                                                           ",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "105": {
                    "type": 2,
                    "descriptor": "<empty>",
                    "status": [
                        1,
                        0,
                        0,
                        160
                    ]
                },
                "106": {
                    "type": 2,
                    "descriptor": "POWER SUPPLY A,CSU1800AP-3-10,N86821000WAKZ,,Artesyn,1800W                                  ",
                    "status": [
                        1,
                        0,
                        0,
                        160
                    ]
                },
                "107": {
                    "type": 2,
                    "descriptor": "POWER SUPPLY B,CSU1800AP-3-10,N86821000CAKZ,,Artesyn,1800W                                  ",
                    "status": [
                        1,
                        0,
                        0,
                        160
                    ]
                },
                "108": {
                    "type": 3,
                    "descriptor": "<empty>",
                    "status": [
                        1,
                        0,
                        0,
                        160
                    ]
                },
                "109": {
                    "type": 3,
                    "descriptor": "FAN ENCL 1      ",
                    "status": [
                        1,
                        2,
                        141,
                        163
                    ]
                },
                "110": {
                    "type": 3,
                    "descriptor": "FAN ENCL 2      ",
                    "status": [
                        1,
                        2,
                        143,
                        163
                    ]
                },
                "111": {
                    "type": 3,
                    "descriptor": "FAN ENCL 3      ",
                    "status": [
                        1,
                        2,
                        144,
                        163
                    ]
                },
                "112": {
                    "type": 3,
                    "descriptor": "FAN ENCL 4      ",
                    "status": [
                        1,
                        2,
                        135,
                        163
                    ]
                },
                "113": {
                    "type": 3,
                    "descriptor": "FAN IOM 1       ",
                    "status": [
                        1,
                        5,
                        248,
                        165
                    ]
                },
                "114": {
                    "type": 3,
                    "descriptor": "FAN IOM 2       ",
                    "status": [
                        1,
                        5,
                        57,
                        165
                    ]
                },
                "115": {
                    "type": 3,
                    "descriptor": "FAN PSU A       ",
                    "status": [
                        1,
                        4,
                        192,
                        165
                    ]
                },
                "116": {
                    "type": 3,
                    "descriptor": "FAN PSU B       ",
                    "status": [
                        1,
                        4,
                        170,
                        165
                    ]
                },
                "117": {
                    "type": 4,
                    "descriptor": "<empty>",
                    "status": [
                        17,
                        0,
                        0,
                        0
                    ]
                },
                "118": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 000   ",
                    "status": [
                        17,
                        0,
                        44,
                        0
                    ]
                },
                "119": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 001   ",
                    "status": [
                        17,
                        0,
                        43,
                        0
                    ]
                },
                "120": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 002   ",
                    "status": [
                        17,
                        0,
                        44,
                        0
                    ]
                },
                "121": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 003   ",
                    "status": [
                        17,
                        0,
                        43,
                        0
                    ]
                },
                "122": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 004   ",
                    "status": [
                        17,
                        0,
                        43,
                        0
                    ]
                },
                "123": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 005   ",
                    "status": [
                        17,
                        0,
                        43,
                        0
                    ]
                },
                "124": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 006   ",
                    "status": [
                        17,
                        0,
                        43,
                        0
                    ]
                },
                "125": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 007   ",
                    "status": [
                        17,
                        0,
                        42,
                        0
                    ]
                },
                "126": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 008   ",
                    "status": [
                        17,
                        0,
                        43,
                        0
                    ]
                },
                "127": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 009   ",
                    "status": [
                        17,
                        0,
                        43,
                        0
                    ]
                },
                "128": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 010   ",
                    "status": [
                        17,
                        0,
                        43,
                        0
                    ]
                },
                "129": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 011   ",
                    "status": [
                        17,
                        0,
                        43,
                        0
                    ]
                },
                "130": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 012   ",
                    "status": [
                        17,
                        0,
                        43,
                        0
                    ]
                },
                "131": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 013   ",
                    "status": [
                        17,
                        0,
                        44,
                        0
                    ]
                },
                "132": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 014   ",
                    "status": [
                        17,
                        0,
                        50,
                        0
                    ]
                },
                "133": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 015   ",
                    "status": [
                        17,
                        0,
                        50,
                        0
                    ]
                },
                "134": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 016   ",
                    "status": [
                        17,
                        0,
                        51,
                        0
                    ]
                },
                "135": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 017   ",
                    "status": [
                        17,
                        0,
                        51,
                        0
                    ]
                },
                "136": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 018   ",
                    "status": [
                        17,
                        0,
                        51,
                        0
                    ]
                },
                "137": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 019   ",
                    "status": [
                        17,
                        0,
                        50,
                        0
                    ]
                },
                "138": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 020   ",
                    "status": [
                        17,
                        0,
                        50,
                        0
                    ]
                },
                "139": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 021   ",
                    "status": [
                        17,
                        0,
                        50,
                        0
                    ]
                },
                "140": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 022   ",
                    "status": [
                        17,
                        0,
                        50,
                        0
                    ]
                },
                "141": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 023   ",
                    "status": [
                        17,
                        0,
                        50,
                        0
                    ]
                },
                "142": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 024   ",
                    "status": [
                        17,
                        0,
                        50,
                        0
                    ]
                },
                "143": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 025   ",
                    "status": [
                        17,
                        0,
                        50,
                        0
                    ]
                },
                "144": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 026   ",
                    "status": [
                        17,
                        0,
                        50,
                        0
                    ]
                },
                "145": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 027   ",
                    "status": [
                        17,
                        0,
                        50,
                        0
                    ]
                },
                "146": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 028   ",
                    "status": [
                        17,
                        0,
                        54,
                        0
                    ]
                },
                "147": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 029   ",
                    "status": [
                        17,
                        0,
                        56,
                        0
                    ]
                },
                "148": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 030   ",
                    "status": [
                        17,
                        0,
                        56,
                        0
                    ]
                },
                "149": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 031   ",
                    "status": [
                        17,
                        0,
                        56,
                        0
                    ]
                },
                "150": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 032   ",
                    "status": [
                        17,
                        0,
                        57,
                        0
                    ]
                },
                "151": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 033   ",
                    "status": [
                        17,
                        0,
                        56,
                        0
                    ]
                },
                "152": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 034   ",
                    "status": [
                        17,
                        0,
                        54,
                        0
                    ]
                },
                "153": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 035   ",
                    "status": [
                        17,
                        0,
                        54,
                        0
                    ]
                },
                "154": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 036   ",
                    "status": [
                        17,
                        0,
                        56,
                        0
                    ]
                },
                "155": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 037   ",
                    "status": [
                        17,
                        0,
                        56,
                        0
                    ]
                },
                "156": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 038   ",
                    "status": [
                        17,
                        0,
                        56,
                        0
                    ]
                },
                "157": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 039   ",
                    "status": [
                        17,
                        0,
                        56,
                        0
                    ]
                },
                "158": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 040   ",
                    "status": [
                        17,
                        0,
                        56,
                        0
                    ]
                },
                "159": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 041   ",
                    "status": [
                        17,
                        0,
                        54,
                        0
                    ]
                },
                "160": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 042   ",
                    "status": [
                        17,
                        0,
                        56,
                        0
                    ]
                },
                "161": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 043   ",
                    "status": [
                        17,
                        0,
                        60,
                        0
                    ]
                },
                "162": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 044   ",
                    "status": [
                        17,
                        0,
                        62,
                        0
                    ]
                },
                "163": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 045   ",
                    "status": [
                        17,
                        0,
                        62,
                        0
                    ]
                },
                "164": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 046   ",
                    "status": [
                        17,
                        0,
                        62,
                        0
                    ]
                },
                "165": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 047   ",
                    "status": [
                        17,
                        0,
                        59,
                        0
                    ]
                },
                "166": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 048   ",
                    "status": [
                        17,
                        0,
                        59,
                        0
                    ]
                },
                "167": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 049   ",
                    "status": [
                        17,
                        0,
                        62,
                        0
                    ]
                },
                "168": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 050   ",
                    "status": [
                        17,
                        0,
                        62,
                        0
                    ]
                },
                "169": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 051   ",
                    "status": [
                        17,
                        0,
                        61,
                        0
                    ]
                },
                "170": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 052   ",
                    "status": [
                        17,
                        0,
                        60,
                        0
                    ]
                },
                "171": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 053   ",
                    "status": [
                        17,
                        0,
                        55,
                        0
                    ]
                },
                "172": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 054   ",
                    "status": [
                        17,
                        0,
                        57,
                        0
                    ]
                },
                "173": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 055   ",
                    "status": [
                        17,
                        0,
                        57,
                        0
                    ]
                },
                "174": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 056   ",
                    "status": [
                        17,
                        0,
                        57,
                        0
                    ]
                },
                "175": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 057   ",
                    "status": [
                        17,
                        0,
                        56,
                        0
                    ]
                },
                "176": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 058   ",
                    "status": [
                        17,
                        0,
                        55,
                        0
                    ]
                },
                "177": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 059   ",
                    "status": [
                        17,
                        0,
                        52,
                        0
                    ]
                },
                "178": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 060   ",
                    "status": [
                        17,
                        0,
                        51,
                        0
                    ]
                },
                "179": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 061   ",
                    "status": [
                        17,
                        0,
                        54,
                        0
                    ]
                },
                "180": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 062   ",
                    "status": [
                        17,
                        0,
                        56,
                        0
                    ]
                },
                "181": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 063   ",
                    "status": [
                        17,
                        0,
                        56,
                        0
                    ]
                },
                "182": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 064   ",
                    "status": [
                        17,
                        0,
                        57,
                        0
                    ]
                },
                "183": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 065   ",
                    "status": [
                        17,
                        0,
                        57,
                        0
                    ]
                },
                "184": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 066   ",
                    "status": [
                        1,
                        0,
                        62,
                        0
                    ]
                },
                "185": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 067   ",
                    "status": [
                        17,
                        0,
                        64,
                        0
                    ]
                },
                "186": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 068   ",
                    "status": [
                        17,
                        0,
                        64,
                        0
                    ]
                },
                "187": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 069   ",
                    "status": [
                        17,
                        0,
                        64,
                        0
                    ]
                },
                "188": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 070   ",
                    "status": [
                        17,
                        0,
                        63,
                        0
                    ]
                },
                "189": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 071   ",
                    "status": [
                        17,
                        0,
                        60,
                        0
                    ]
                },
                "190": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 072   ",
                    "status": [
                        17,
                        0,
                        58,
                        0
                    ]
                },
                "191": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 073   ",
                    "status": [
                        17,
                        0,
                        62,
                        0
                    ]
                },
                "192": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 074   ",
                    "status": [
                        17,
                        0,
                        63,
                        0
                    ]
                },
                "193": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 075   ",
                    "status": [
                        17,
                        0,
                        63,
                        0
                    ]
                },
                "194": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 076   ",
                    "status": [
                        17,
                        0,
                        63,
                        0
                    ]
                },
                "195": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 077   ",
                    "status": [
                        17,
                        0,
                        61,
                        0
                    ]
                },
                "196": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 078   ",
                    "status": [
                        17,
                        0,
                        63,
                        0
                    ]
                },
                "197": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 079   ",
                    "status": [
                        17,
                        0,
                        67,
                        0
                    ]
                },
                "198": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 080   ",
                    "status": [
                        17,
                        0,
                        68,
                        0
                    ]
                },
                "199": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 081   ",
                    "status": [
                        17,
                        0,
                        68,
                        0
                    ]
                },
                "200": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 082   ",
                    "status": [
                        17,
                        0,
                        67,
                        0
                    ]
                },
                "201": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 083   ",
                    "status": [
                        17,
                        0,
                        65,
                        0
                    ]
                },
                "202": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 084   ",
                    "status": [
                        17,
                        0,
                        62,
                        0
                    ]
                },
                "203": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 085   ",
                    "status": [
                        17,
                        0,
                        65,
                        0
                    ]
                },
                "204": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 086   ",
                    "status": [
                        17,
                        0,
                        67,
                        0
                    ]
                },
                "205": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 087   ",
                    "status": [
                        17,
                        0,
                        67,
                        0
                    ]
                },
                "206": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 088   ",
                    "status": [
                        17,
                        0,
                        66,
                        0
                    ]
                },
                "207": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 089   ",
                    "status": [
                        17,
                        0,
                        63,
                        0
                    ]
                },
                "208": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 090   ",
                    "status": [
                        17,
                        0,
                        61,
                        0
                    ]
                },
                "209": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 091   ",
                    "status": [
                        17,
                        0,
                        65,
                        0
                    ]
                },
                "210": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 092   ",
                    "status": [
                        17,
                        0,
                        68,
                        0
                    ]
                },
                "211": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 093   ",
                    "status": [
                        17,
                        0,
                        68,
                        0
                    ]
                },
                "212": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 094   ",
                    "status": [
                        1,
                        0,
                        67,
                        0
                    ]
                },
                "213": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 095   ",
                    "status": [
                        17,
                        0,
                        66,
                        0
                    ]
                },
                "214": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 096   ",
                    "status": [
                        17,
                        0,
                        62,
                        0
                    ]
                },
                "215": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 097   ",
                    "status": [
                        17,
                        0,
                        65,
                        0
                    ]
                },
                "216": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 098   ",
                    "status": [
                        17,
                        0,
                        66,
                        0
                    ]
                },
                "217": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 099   ",
                    "status": [
                        17,
                        0,
                        65,
                        0
                    ]
                },
                "218": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 100   ",
                    "status": [
                        17,
                        0,
                        64,
                        0
                    ]
                },
                "219": {
                    "type": 4,
                    "descriptor": "TEMP SLOT 101   ",
                    "status": [
                        17,
                        0,
                        62,
                        0
                    ]
                },
                "220": {
                    "type": 4,
                    "descriptor": "TEMP IOM A      ",
                    "status": [
                        1,
                        0,
                        70,
                        0
                    ]
                },
                "221": {
                    "type": 4,
                    "descriptor": "TEMP IOM B      ",
                    "status": [
                        1,
                        0,
                        73,
                        0
                    ]
                },
                "222": {
                    "type": 4,
                    "descriptor": "TEMP BB 60 1    ",
                    "status": [
                        1,
                        0,
                        47,
                        0
                    ]
                },
                "223": {
                    "type": 4,
                    "descriptor": "TEMP BB 60 2    ",
                    "status": [
                        1,
                        0,
                        47,
                        0
                    ]
                },
                "224": {
                    "type": 4,
                    "descriptor": "TEMP BB 42 1    ",
                    "status": [
                        1,
                        0,
                        37,
                        0
                    ]
                },
                "225": {
                    "type": 4,
                    "descriptor": "TEMP BB 42 2    ",
                    "status": [
                        1,
                        0,
                        37,
                        0
                    ]
                },
                "226": {
                    "type": 4,
                    "descriptor": "TEMP PRI A DIE  ",
                    "status": [
                        1,
                        0,
                        83,
                        0
                    ]
                },
                "227": {
                    "type": 4,
                    "descriptor": "TEMP SEC1 A DIE ",
                    "status": [
                        1,
                        0,
                        105,
                        0
                    ]
                },
                "228": {
                    "type": 4,
                    "descriptor": "TEMP SEC2 A DIE ",
                    "status": [
                        1,
                        0,
                        83,
                        0
                    ]
                },
                "229": {
                    "type": 4,
                    "descriptor": "TEMP PRI A MEM  ",
                    "status": [
                        1,
                        0,
                        68,
                        0
                    ]
                },
                "230": {
                    "type": 4,
                    "descriptor": "TEMP SEC1 A MEM ",
                    "status": [
                        1,
                        0,
                        68,
                        0
                    ]
                },
                "231": {
                    "type": 4,
                    "descriptor": "TEMP SEC2 A MEM ",
                    "status": [
                        1,
                        0,
                        59,
                        0
                    ]
                },
                "232": {
                    "type": 4,
                    "descriptor": "TEMP PRI B DIE  ",
                    "status": [
                        1,
                        0,
                        86,
                        0
                    ]
                },
                "233": {
                    "type": 4,
                    "descriptor": "TEMP SEC1 B DIE ",
                    "status": [
                        1,
                        0,
                        106,
                        0
                    ]
                },
                "234": {
                    "type": 4,
                    "descriptor": "TEMP SEC2 B DIE ",
                    "status": [
                        1,
                        0,
                        91,
                        0
                    ]
                },
                "235": {
                    "type": 4,
                    "descriptor": "TEMP PRI B MEM  ",
                    "status": [
                        1,
                        0,
                        70,
                        0
                    ]
                },
                "236": {
                    "type": 4,
                    "descriptor": "TEMP SEC1 B MEM ",
                    "status": [
                        1,
                        0,
                        71,
                        0
                    ]
                },
                "237": {
                    "type": 4,
                    "descriptor": "TEMP SEC2 B MEM ",
                    "status": [
                        1,
                        0,
                        59,
                        0
                    ]
                },
                "238": {
                    "type": 4,
                    "descriptor": "TEMP IOM A 5V   ",
                    "status": [
                        1,
                        0,
                        66,
                        0
                    ]
                },
                "239": {
                    "type": 4,
                    "descriptor": "TEMP IOM B 5V   ",
                    "status": [
                        1,
                        0,
                        72,
                        0
                    ]
                },
                "240": {
                    "type": 4,
                    "descriptor": "TEMP PSU A AMB  ",
                    "status": [
                        1,
                        0,
                        62,
                        0
                    ]
                },
                "241": {
                    "type": 4,
                    "descriptor": "TEMP PSU A HOT  ",
                    "status": [
                        1,
                        0,
                        81,
                        0
                    ]
                },
                "242": {
                    "type": 4,
                    "descriptor": "TEMP PSU A PRI  ",
                    "status": [
                        1,
                        0,
                        71,
                        0
                    ]
                },
                "243": {
                    "type": 4,
                    "descriptor": "TEMP PSU B AMB  ",
                    "status": [
                        1,
                        0,
                        52,
                        0
                    ]
                },
                "244": {
                    "type": 4,
                    "descriptor": "TEMP PSU B HOT  ",
                    "status": [
                        1,
                        0,
                        84,
                        0
                    ]
                },
                "245": {
                    "type": 4,
                    "descriptor": "TEMP PSU B PRI  ",
                    "status": [
                        1,
                        0,
                        72,
                        0
                    ]
                },
                "246": {
                    "type": 7,
                    "descriptor": "<empty>",
                    "status": [
                        1,
                        0,
                        1,
                        128
                    ]
                },
                "247": {
                    "type": 7,
                    "descriptor": "ESCE IOMA,1EA0484-C1          ,THCCT03821EG014F    ,5000CCAB0511683C,,00:0C:CA:07:45:77,3.1.11                                                              ",
                    "status": [
                        1,
                        16,
                        1,
                        128
                    ]
                },
                "248": {
                    "type": 7,
                    "descriptor": "ESCE IOMB,1EA0484-C1          ,THCCT03821EG0150    ,5000CCAB0511687C,,00:0C:CA:07:45:6F,3.1.11                                                              ",
                    "status": [
                        1,
                        16,
                        0,
                        128
                    ]
                },
                "249": {
                    "type": 24,
                    "descriptor": "<empty>",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "250": {
                    "type": 24,
                    "descriptor": "EXP IOMA 0,3010-007,5000CCAB0511683D",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "251": {
                    "type": 24,
                    "descriptor": "EXP IOMA 1,3010-007,5000CCAB0511683F",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "252": {
                    "type": 24,
                    "descriptor": "EXP IOMA 2,3010-007,5000CCAB0511687F",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "253": {
                    "type": 24,
                    "descriptor": "EXP IOMB 0,3010-007,5000CCAB0511687D",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "254": {
                    "type": 24,
                    "descriptor": "EXP IOMB 1,3010-007,5000CCAB05116879",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "255": {
                    "type": 24,
                    "descriptor": "EXP IOMB 2,3010-007,5000CCAB0511687B",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "256": {
                    "type": 25,
                    "descriptor": "<empty>",
                    "status": [
                        5,
                        0,
                        0,
                        0
                    ]
                },
                "257": {
                    "type": 25,
                    "descriptor": "CONN HOST 00    ",
                    "status": [
                        1,
                        5,
                        255,
                        128
                    ]
                },
                "258": {
                    "type": 25,
                    "descriptor": "CONN HOST 01    ",
                    "status": [
                        5,
                        5,
                        255,
                        0
                    ]
                },
                "259": {
                    "type": 25,
                    "descriptor": "CONN HOST 02    ",
                    "status": [
                        5,
                        5,
                        255,
                        0
                    ]
                },
                "260": {
                    "type": 25,
                    "descriptor": "CONN HOST 03    ",
                    "status": [
                        5,
                        5,
                        255,
                        0
                    ]
                },
                "261": {
                    "type": 25,
                    "descriptor": "CONN HOST 04    ",
                    "status": [
                        5,
                        5,
                        255,
                        0
                    ]
                },
                "262": {
                    "type": 25,
                    "descriptor": "CONN HOST 05    ",
                    "status": [
                        5,
                        5,
                        255,
                        0
                    ]
                },
                "263": {
                    "type": 25,
                    "descriptor": "CONN HOST 06    ",
                    "status": [
                        1,
                        5,
                        255,
                        128
                    ]
                },
                "264": {
                    "type": 25,
                    "descriptor": "CONN HOST 07    ",
                    "status": [
                        5,
                        5,
                        255,
                        0
                    ]
                },
                "265": {
                    "type": 25,
                    "descriptor": "CONN HOST 08    ",
                    "status": [
                        5,
                        5,
                        255,
                        0
                    ]
                },
                "266": {
                    "type": 25,
                    "descriptor": "CONN HOST 09    ",
                    "status": [
                        5,
                        5,
                        255,
                        0
                    ]
                },
                "267": {
                    "type": 25,
                    "descriptor": "CONN HOST 10    ",
                    "status": [
                        5,
                        5,
                        255,
                        0
                    ]
                },
                "268": {
                    "type": 25,
                    "descriptor": "CONN HOST 11    ",
                    "status": [
                        5,
                        5,
                        255,
                        0
                    ]
                },
                "269": {
                    "type": 18,
                    "descriptor": "<empty>",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "270": {
                    "type": 18,
                    "descriptor": "VOLT PSU A AC   ",
                    "status": [
                        1,
                        0,
                        78,
                        32
                    ]
                },
                "271": {
                    "type": 18,
                    "descriptor": "VOLT PSU A 12V  ",
                    "status": [
                        1,
                        0,
                        4,
                        201
                    ]
                },
                "272": {
                    "type": 18,
                    "descriptor": "VOLT PSU B AC   ",
                    "status": [
                        1,
                        0,
                        78,
                        132
                    ]
                },
                "273": {
                    "type": 18,
                    "descriptor": "VOLT PSU B 12V  ",
                    "status": [
                        1,
                        0,
                        4,
                        204
                    ]
                },
                "274": {
                    "type": 18,
                    "descriptor": "VOLT IOM A 5V   ",
                    "status": [
                        1,
                        0,
                        1,
                        247
                    ]
                },
                "275": {
                    "type": 18,
                    "descriptor": "VOLT IOM A 12V  ",
                    "status": [
                        1,
                        0,
                        4,
                        176
                    ]
                },
                "276": {
                    "type": 18,
                    "descriptor": "VOLT IOM B 5V   ",
                    "status": [
                        1,
                        0,
                        1,
                        247
                    ]
                },
                "277": {
                    "type": 18,
                    "descriptor": "VOLT IOM B 12V  ",
                    "status": [
                        1,
                        0,
                        4,
                        176
                    ]
                },
                "278": {
                    "type": 19,
                    "descriptor": "<empty>",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "279": {
                    "type": 19,
                    "descriptor": "CURR PSU A IN   ",
                    "status": [
                        1,
                        0,
                        0,
                        216
                    ]
                },
                "280": {
                    "type": 19,
                    "descriptor": "CURR PSU A OUT  ",
                    "status": [
                        1,
                        0,
                        12,
                        184
                    ]
                },
                "281": {
                    "type": 19,
                    "descriptor": "CURR PSU B IN   ",
                    "status": [
                        1,
                        0,
                        0,
                        219
                    ]
                },
                "282": {
                    "type": 19,
                    "descriptor": "CURR PSU B OUT  ",
                    "status": [
                        1,
                        0,
                        12,
                        247
                    ]
                },
                "283": {
                    "type": 19,
                    "descriptor": "CURR IOM A 12V  ",
                    "status": [
                        1,
                        0,
                        5,
                        78
                    ]
                },
                "284": {
                    "type": 19,
                    "descriptor": "CURR IOM A 5V   ",
                    "status": [
                        1,
                        0,
                        7,
                        208
                    ]
                },
                "285": {
                    "type": 19,
                    "descriptor": "CURR IOM B 12V  ",
                    "status": [
                        1,
                        0,
                        5,
                        183
                    ]
                },
                "286": {
                    "type": 19,
                    "descriptor": "CURR IOM B 5V   ",
                    "status": [
                        1,
                        0,
                        8,
                        2
                    ]
                },
                "287": {
                    "type": 5,
                    "descriptor": "<empty>",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                },
                "288": {
                    "type": 5,
                    "descriptor": "ENCLOSURE COVER ",
                    "status": [
                        1,
                        0,
                        0,
                        0
                    ]
                }
            }
        },
        {  # ES102 JBOD enclosure_class.py::Enclosure.asdict() output
            "name": "HGST H4102-J 3010",
            "model": "ES102",
            "controller": False,
            "dmi": "TRUENAS-M60-HA",
            "status": [
                "INFO"
            ],
            "id": "5000ccab05116800",
            "vendor": "HGST",
            "product": "H4102-J",
            "revision": "3010",
            "bsg": "/dev/bsg/19:0:309:0",
            "sg": "/dev/sg1155",
            "pci": "19:0:309:0",
            "elements": {
                "Array Device Slot": {
                    "1": {
                        "descriptor": "SLOT 000,3FG1KMYV",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasw",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot1",
                            "slot": 1
                        }
                    },
                    "2": {
                        "descriptor": "SLOT 001,3FJ3J58T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasx",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot2",
                            "slot": 2
                        }
                    },
                    "3": {
                        "descriptor": "SLOT 002,3FHXK2YT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasy",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot3",
                            "slot": 3
                        }
                    },
                    "4": {
                        "descriptor": "SLOT 003,3FJG59GT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasz",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot4",
                            "slot": 4
                        }
                    },
                    "5": {
                        "descriptor": "SLOT 004,3FJ1S32T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdata",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot5",
                            "slot": 5
                        }
                    },
                    "6": {
                        "descriptor": "SLOT 005,3FJJ76GT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatb",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot6",
                            "slot": 6
                        }
                    },
                    "7": {
                        "descriptor": "SLOT 006,3FHXGM8T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatc",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot7",
                            "slot": 7
                        }
                    },
                    "8": {
                        "descriptor": "SLOT 007,3FG1KLKV",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatd",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot8",
                            "slot": 8
                        }
                    },
                    "9": {
                        "descriptor": "SLOT 008,3FJ2NY8T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdate",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot9",
                            "slot": 9
                        }
                    },
                    "10": {
                        "descriptor": "SLOT 009,3FJ2LYPT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatf",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot10",
                            "slot": 10
                        }
                    },
                    "11": {
                        "descriptor": "SLOT 010,3FJJZZ4T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatg",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot11",
                            "slot": 11
                        }
                    },
                    "12": {
                        "descriptor": "SLOT 011,3FH53S0T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdath",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot12",
                            "slot": 12
                        }
                    },
                    "13": {
                        "descriptor": "SLOT 012,3FJJ187T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdati",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot13",
                            "slot": 13
                        }
                    },
                    "14": {
                        "descriptor": "SLOT 013,3FJ0DURT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatj",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot14",
                            "slot": 14
                        }
                    },
                    "15": {
                        "descriptor": "SLOT 014,3FJ30KNT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatk",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot15",
                            "slot": 15
                        }
                    },
                    "16": {
                        "descriptor": "SLOT 015,3FJK5B3T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatl",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot16",
                            "slot": 16
                        }
                    },
                    "17": {
                        "descriptor": "SLOT 016,3FG3RGDV",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatm",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot17",
                            "slot": 17
                        }
                    },
                    "18": {
                        "descriptor": "SLOT 017,3FJ28KNT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatn",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot18",
                            "slot": 18
                        }
                    },
                    "19": {
                        "descriptor": "SLOT 018,3FH3Z5PT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdato",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot19",
                            "slot": 19
                        }
                    },
                    "20": {
                        "descriptor": "SLOT 019,3FJ33PZT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatp",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot20",
                            "slot": 20
                        }
                    },
                    "21": {
                        "descriptor": "SLOT 020,3FJ1M3AT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatq",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot21",
                            "slot": 21
                        }
                    },
                    "22": {
                        "descriptor": "SLOT 021,3FJ2WG5T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatr",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot22",
                            "slot": 22
                        }
                    },
                    "23": {
                        "descriptor": "SLOT 022,3FJK5M6T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdats",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot23",
                            "slot": 23
                        }
                    },
                    "24": {
                        "descriptor": "SLOT 023,3FJ2H8YT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatt",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot24",
                            "slot": 24
                        }
                    },
                    "25": {
                        "descriptor": "SLOT 024,3FHZRBXT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatu",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot25",
                            "slot": 25
                        }
                    },
                    "26": {
                        "descriptor": "SLOT 025,3RHSMW3A",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatv",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot26",
                            "slot": 26
                        }
                    },
                    "27": {
                        "descriptor": "SLOT 026,3FJ1U45T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatw",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot27",
                            "slot": 27
                        }
                    },
                    "28": {
                        "descriptor": "SLOT 027,3FHLT9RT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatx",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot28",
                            "slot": 28
                        }
                    },
                    "29": {
                        "descriptor": "SLOT 028,3FJ2LMDT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaty",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot29",
                            "slot": 29
                        }
                    },
                    "30": {
                        "descriptor": "SLOT 029,3FJ28Y8T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdatz",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot30",
                            "slot": 30
                        }
                    },
                    "31": {
                        "descriptor": "SLOT 030,3FH4VDMT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaua",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot31",
                            "slot": 31
                        }
                    },
                    "32": {
                        "descriptor": "SLOT 031,3FJ2A3TT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaub",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot32",
                            "slot": 32
                        }
                    },
                    "33": {
                        "descriptor": "SLOT 032,3FHR3PJT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdauc",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot33",
                            "slot": 33
                        }
                    },
                    "34": {
                        "descriptor": "SLOT 033,3FHP4AVT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaud",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot34",
                            "slot": 34
                        }
                    },
                    "35": {
                        "descriptor": "SLOT 034,3FJ2G3YT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaue",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot35",
                            "slot": 35
                        }
                    },
                    "36": {
                        "descriptor": "SLOT 035,3FHLKBRT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdauf",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot36",
                            "slot": 36
                        }
                    },
                    "37": {
                        "descriptor": "SLOT 036,3FHY7VST",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaug",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot37",
                            "slot": 37
                        }
                    },
                    "38": {
                        "descriptor": "SLOT 037,3FHYE9YT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdauh",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot38",
                            "slot": 38
                        }
                    },
                    "39": {
                        "descriptor": "SLOT 038,3FH4UY6T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaui",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot39",
                            "slot": 39
                        }
                    },
                    "40": {
                        "descriptor": "SLOT 039,3FHMJ0DT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdauj",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot40",
                            "slot": 40
                        }
                    },
                    "41": {
                        "descriptor": "SLOT 040,3FJ2P79T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdauk",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot41",
                            "slot": 41
                        }
                    },
                    "42": {
                        "descriptor": "SLOT 041,3FHZRBZT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaul",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot42",
                            "slot": 42
                        }
                    },
                    "43": {
                        "descriptor": "SLOT 042,3FHYGT9T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaqx",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot43",
                            "slot": 43
                        }
                    },
                    "44": {
                        "descriptor": "SLOT 043,3FJJZZ7T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaum",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot44",
                            "slot": 44
                        }
                    },
                    "45": {
                        "descriptor": "SLOT 044,3FJ2MSXT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaqy",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot45",
                            "slot": 45
                        }
                    },
                    "46": {
                        "descriptor": "SLOT 045,3FG1KKPV",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaun",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot46",
                            "slot": 46
                        }
                    },
                    "47": {
                        "descriptor": "SLOT 046,3FHYYKGT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdauo",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot47",
                            "slot": 47
                        }
                    },
                    "48": {
                        "descriptor": "SLOT 047,3FHXGWZT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaup",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot48",
                            "slot": 48
                        }
                    },
                    "49": {
                        "descriptor": "SLOT 048,3FJ2Z5LT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdauq",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot49",
                            "slot": 49
                        }
                    },
                    "50": {
                        "descriptor": "SLOT 049,3FJ1781T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdauu",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot50",
                            "slot": 50
                        }
                    },
                    "51": {
                        "descriptor": "SLOT 050,3FH83XZT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaur",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot51",
                            "slot": 51
                        }
                    },
                    "52": {
                        "descriptor": "SLOT 051,3RHLZ4RA",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaus",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot52",
                            "slot": 52
                        }
                    },
                    "53": {
                        "descriptor": "SLOT 052,3FJ2WPAT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaut",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot53",
                            "slot": 53
                        }
                    },
                    "54": {
                        "descriptor": "SLOT 053,3FJ1411T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaqz",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot54",
                            "slot": 54
                        }
                    },
                    "55": {
                        "descriptor": "SLOT 054,3FG3RB8V",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdara",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot55",
                            "slot": 55
                        }
                    },
                    "56": {
                        "descriptor": "SLOT 055,3FJ2KNDT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdarb",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot56",
                            "slot": 56
                        }
                    },
                    "57": {
                        "descriptor": "SLOT 056,3FHP6BPT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdarc",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot57",
                            "slot": 57
                        }
                    },
                    "58": {
                        "descriptor": "SLOT 057,3FHDKGTT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdard",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot58",
                            "slot": 58
                        }
                    },
                    "59": {
                        "descriptor": "SLOT 058,3FJ2W4UT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdare",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot59",
                            "slot": 59
                        }
                    },
                    "60": {
                        "descriptor": "SLOT 059,3FJ1441T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdarf",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot60",
                            "slot": 60
                        }
                    },
                    "61": {
                        "descriptor": "SLOT 060,3FJ2S29T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdarg",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot61",
                            "slot": 61
                        }
                    },
                    "62": {
                        "descriptor": "SLOT 061,3FHY77PT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdarh",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot62",
                            "slot": 62
                        }
                    },
                    "63": {
                        "descriptor": "SLOT 062,3FHPWTJT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdari",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot63",
                            "slot": 63
                        }
                    },
                    "64": {
                        "descriptor": "SLOT 063,3FJ2S2VT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdarj",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot64",
                            "slot": 64
                        }
                    },
                    "65": {
                        "descriptor": "SLOT 064,3FH260RT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdark",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot65",
                            "slot": 65
                        }
                    },
                    "66": {
                        "descriptor": "SLOT 065,3FHP66DT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdarl",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot66",
                            "slot": 66
                        }
                    },
                    "67": {
                        "descriptor": "SLOT 066,3FHPYD1T",
                        "status": "OK",
                        "value": None,
                        "value_raw": 16777216,
                        "dev": "sdarm",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot67",
                            "slot": 67
                        }
                    },
                    "68": {
                        "descriptor": "SLOT 067,3FJ2MW6T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdarn",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot68",
                            "slot": 68
                        }
                    },
                    "69": {
                        "descriptor": "SLOT 068,3FJ29WNT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaro",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot69",
                            "slot": 69
                        }
                    },
                    "70": {
                        "descriptor": "SLOT 069,3FJ2S30T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdarp",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot70",
                            "slot": 70
                        }
                    },
                    "71": {
                        "descriptor": "SLOT 070,3FJ1V6PT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdarq",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot71",
                            "slot": 71
                        }
                    },
                    "72": {
                        "descriptor": "SLOT 071,3FJ1WEWT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdarr",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot72",
                            "slot": 72
                        }
                    },
                    "73": {
                        "descriptor": "SLOT 072,3FJ15PGT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdars",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot73",
                            "slot": 73
                        }
                    },
                    "74": {
                        "descriptor": "SLOT 073,3FJJX6DT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdart",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot74",
                            "slot": 74
                        }
                    },
                    "75": {
                        "descriptor": "SLOT 074,3FJ309HT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdaru",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot75",
                            "slot": 75
                        }
                    },
                    "76": {
                        "descriptor": "SLOT 075,3FJ2H29T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdarv",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot76",
                            "slot": 76
                        }
                    },
                    "77": {
                        "descriptor": "SLOT 076,3FJ1433T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdarw",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot77",
                            "slot": 77
                        }
                    },
                    "78": {
                        "descriptor": "SLOT 077,3FJ2KL9T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdarx",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot78",
                            "slot": 78
                        }
                    },
                    "79": {
                        "descriptor": "SLOT 078,3FJ19DTT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdary",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot79",
                            "slot": 79
                        }
                    },
                    "80": {
                        "descriptor": "SLOT 079,3FJ2P37T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdarz",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot80",
                            "slot": 80
                        }
                    },
                    "81": {
                        "descriptor": "SLOT 080,3FHYY0ZT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasa",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot81",
                            "slot": 81
                        }
                    },
                    "82": {
                        "descriptor": "SLOT 081,3FHN8LKT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasb",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot82",
                            "slot": 82
                        }
                    },
                    "83": {
                        "descriptor": "SLOT 082,3FJ1J3GT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasc",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot83",
                            "slot": 83
                        }
                    },
                    "84": {
                        "descriptor": "SLOT 083,3FHYLP7T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasd",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot84",
                            "slot": 84
                        }
                    },
                    "85": {
                        "descriptor": "SLOT 084,3FJ15SRT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdase",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot85",
                            "slot": 85
                        }
                    },
                    "86": {
                        "descriptor": "SLOT 085,3FHKW9GT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasf",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot86",
                            "slot": 86
                        }
                    },
                    "87": {
                        "descriptor": "SLOT 086,3FHYEVJT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdash",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot87",
                            "slot": 87
                        }
                    },
                    "88": {
                        "descriptor": "SLOT 087,3FJ2A5VT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasg",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot88",
                            "slot": 88
                        }
                    },
                    "89": {
                        "descriptor": "SLOT 088,3FJ2MU9T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasi",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot89",
                            "slot": 89
                        }
                    },
                    "90": {
                        "descriptor": "SLOT 089,3FJ197HT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasj",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot90",
                            "slot": 90
                        }
                    },
                    "91": {
                        "descriptor": "SLOT 090,3FJ29S7T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdask",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot91",
                            "slot": 91
                        }
                    },
                    "92": {
                        "descriptor": "SLOT 091,3FJ2P7DT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasl",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot92",
                            "slot": 92
                        }
                    },
                    "93": {
                        "descriptor": "SLOT 092,3FHY8KTT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasm",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot93",
                            "slot": 93
                        }
                    },
                    "94": {
                        "descriptor": "SLOT 093,3FHY81RT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasn",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot94",
                            "slot": 94
                        }
                    },
                    "95": {
                        "descriptor": "SLOT 094,3FJ153KT",
                        "status": "OK",
                        "value": None,
                        "value_raw": 16777216,
                        "dev": "sdaso",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot95",
                            "slot": 95
                        }
                    },
                    "96": {
                        "descriptor": "SLOT 095,3FJ17XBT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasp",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot96",
                            "slot": 96
                        }
                    },
                    "97": {
                        "descriptor": "SLOT 096,3FJ3J3ST",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasq",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot97",
                            "slot": 97
                        }
                    },
                    "98": {
                        "descriptor": "SLOT 097,3FJ2MU0T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasr",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot98",
                            "slot": 98
                        }
                    },
                    "99": {
                        "descriptor": "SLOT 098,3FJ2A7LT",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdass",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot99",
                            "slot": 99
                        }
                    },
                    "100": {
                        "descriptor": "SLOT 099,3FJ29V3T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdast",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot100",
                            "slot": 100
                        }
                    },
                    "101": {
                        "descriptor": "SLOT 100,3FHYW3ST",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasu",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot101",
                            "slot": 101
                        }
                    },
                    "102": {
                        "descriptor": "SLOT 101,3FJ2S36T",
                        "status": "OK, Swapped",
                        "value": None,
                        "value_raw": 285212672,
                        "dev": "sdasv",
                        "original": {
                            "enclosure_id": "5000ccab05116800",
                            "enclosure_sg": "/dev/sg1155",
                            "enclosure_bsg": "/dev/bsg/19:0:309:0",
                            "descriptor": "slot102",
                            "slot": 102
                        }
                    }
                },
                "Enclosure": {
                    "104": {
                        "descriptor": "ENCLOSURE,1ES1846-A3,THCCT03921EA0015,1EB1173-A1,THCCT03721EJ1945",
                        "status": "OK",
                        "value": None,
                        "value_raw": 16777216
                    }
                },
                "Power Supply": {
                    "106": {
                        "descriptor": "POWER SUPPLY A,CSU1800AP-3-10,N86821000WAKZ,,Artesyn,1800W",
                        "status": "OK",
                        "value": "Hot swap, RQST on",
                        "value_raw": 16777376
                    },
                    "107": {
                        "descriptor": "POWER SUPPLY B,CSU1800AP-3-10,N86821000CAKZ,,Artesyn,1800W",
                        "status": "OK",
                        "value": "Hot swap, RQST on",
                        "value_raw": 16777376
                    }
                },
                "Cooling": {
                    "109": {
                        "descriptor": "FAN ENCL 1",
                        "status": "OK",
                        "value": "4240 RPM",
                        "value_raw": 16885922
                    },
                    "110": {
                        "descriptor": "FAN ENCL 2",
                        "status": "OK",
                        "value": "4230 RPM",
                        "value_raw": 16885666
                    },
                    "111": {
                        "descriptor": "FAN ENCL 3",
                        "status": "OK",
                        "value": "4210 RPM",
                        "value_raw": 16885154
                    },
                    "112": {
                        "descriptor": "FAN ENCL 4",
                        "status": "OK",
                        "value": "4200 RPM",
                        "value_raw": 16884898
                    },
                    "113": {
                        "descriptor": "FAN IOM 1",
                        "status": "OK",
                        "value": "18730 RPM",
                        "value_raw": 17256870
                    },
                    "114": {
                        "descriptor": "FAN IOM 2",
                        "status": "OK",
                        "value": "16300 RPM",
                        "value_raw": 17194662
                    },
                    "115": {
                        "descriptor": "FAN PSU A",
                        "status": "OK",
                        "value": "20470 RPM",
                        "value_raw": 17301414
                    },
                    "116": {
                        "descriptor": "FAN PSU B",
                        "status": "OK",
                        "value": "20470 RPM",
                        "value_raw": 17301414
                    }
                },
                "Temperature Sensors": {
                    "118": {
                        "descriptor": "TEMP SLOT 000",
                        "status": "OK, Swapped",
                        "value": "26C",
                        "value_raw": 285224448
                    },
                    "119": {
                        "descriptor": "TEMP SLOT 001",
                        "status": "OK, Swapped",
                        "value": "26C",
                        "value_raw": 285224448
                    },
                    "120": {
                        "descriptor": "TEMP SLOT 002",
                        "status": "OK, Swapped",
                        "value": "26C",
                        "value_raw": 285224448
                    },
                    "121": {
                        "descriptor": "TEMP SLOT 003",
                        "status": "OK, Swapped",
                        "value": "26C",
                        "value_raw": 285224448
                    },
                    "122": {
                        "descriptor": "TEMP SLOT 004",
                        "status": "OK, Swapped",
                        "value": "26C",
                        "value_raw": 285224448
                    },
                    "123": {
                        "descriptor": "TEMP SLOT 005",
                        "status": "OK, Swapped",
                        "value": "26C",
                        "value_raw": 285224448
                    },
                    "124": {
                        "descriptor": "TEMP SLOT 006",
                        "status": "OK, Swapped",
                        "value": "26C",
                        "value_raw": 285224448
                    },
                    "125": {
                        "descriptor": "TEMP SLOT 007",
                        "status": "OK, Swapped",
                        "value": "25C",
                        "value_raw": 285224192
                    },
                    "126": {
                        "descriptor": "TEMP SLOT 008",
                        "status": "OK, Swapped",
                        "value": "26C",
                        "value_raw": 285224448
                    },
                    "127": {
                        "descriptor": "TEMP SLOT 009",
                        "status": "OK, Swapped",
                        "value": "26C",
                        "value_raw": 285224448
                    },
                    "128": {
                        "descriptor": "TEMP SLOT 010",
                        "status": "OK, Swapped",
                        "value": "26C",
                        "value_raw": 285224448
                    },
                    "129": {
                        "descriptor": "TEMP SLOT 011",
                        "status": "OK, Swapped",
                        "value": "26C",
                        "value_raw": 285224448
                    },
                    "130": {
                        "descriptor": "TEMP SLOT 012",
                        "status": "OK, Swapped",
                        "value": "26C",
                        "value_raw": 285224448
                    },
                    "131": {
                        "descriptor": "TEMP SLOT 013",
                        "status": "OK, Swapped",
                        "value": "26C",
                        "value_raw": 285224448
                    },
                    "132": {
                        "descriptor": "TEMP SLOT 014",
                        "status": "OK, Swapped",
                        "value": "31C",
                        "value_raw": 285225728
                    },
                    "133": {
                        "descriptor": "TEMP SLOT 015",
                        "status": "OK, Swapped",
                        "value": "32C",
                        "value_raw": 285225984
                    },
                    "134": {
                        "descriptor": "TEMP SLOT 016",
                        "status": "OK, Swapped",
                        "value": "32C",
                        "value_raw": 285225984
                    },
                    "135": {
                        "descriptor": "TEMP SLOT 017",
                        "status": "OK, Swapped",
                        "value": "33C",
                        "value_raw": 285226240
                    },
                    "136": {
                        "descriptor": "TEMP SLOT 018",
                        "status": "OK, Swapped",
                        "value": "32C",
                        "value_raw": 285225984
                    },
                    "137": {
                        "descriptor": "TEMP SLOT 019",
                        "status": "OK, Swapped",
                        "value": "32C",
                        "value_raw": 285225984
                    },
                    "138": {
                        "descriptor": "TEMP SLOT 020",
                        "status": "OK, Swapped",
                        "value": "32C",
                        "value_raw": 285225984
                    },
                    "139": {
                        "descriptor": "TEMP SLOT 021",
                        "status": "OK, Swapped",
                        "value": "32C",
                        "value_raw": 285225984
                    },
                    "140": {
                        "descriptor": "TEMP SLOT 022",
                        "status": "OK, Swapped",
                        "value": "32C",
                        "value_raw": 285225984
                    },
                    "141": {
                        "descriptor": "TEMP SLOT 023",
                        "status": "OK, Swapped",
                        "value": "32C",
                        "value_raw": 285225984
                    },
                    "142": {
                        "descriptor": "TEMP SLOT 024",
                        "status": "OK, Swapped",
                        "value": "32C",
                        "value_raw": 285225984
                    },
                    "143": {
                        "descriptor": "TEMP SLOT 025",
                        "status": "OK, Swapped",
                        "value": "32C",
                        "value_raw": 285225984
                    },
                    "144": {
                        "descriptor": "TEMP SLOT 026",
                        "status": "OK, Swapped",
                        "value": "32C",
                        "value_raw": 285225984
                    },
                    "145": {
                        "descriptor": "TEMP SLOT 027",
                        "status": "OK, Swapped",
                        "value": "31C",
                        "value_raw": 285225728
                    },
                    "146": {
                        "descriptor": "TEMP SLOT 028",
                        "status": "OK, Swapped",
                        "value": "35C",
                        "value_raw": 285226752
                    },
                    "147": {
                        "descriptor": "TEMP SLOT 029",
                        "status": "OK, Swapped",
                        "value": "37C",
                        "value_raw": 285227264
                    },
                    "148": {
                        "descriptor": "TEMP SLOT 030",
                        "status": "OK, Swapped",
                        "value": "38C",
                        "value_raw": 285227520
                    },
                    "149": {
                        "descriptor": "TEMP SLOT 031",
                        "status": "OK, Swapped",
                        "value": "38C",
                        "value_raw": 285227520
                    },
                    "150": {
                        "descriptor": "TEMP SLOT 032",
                        "status": "OK, Swapped",
                        "value": "38C",
                        "value_raw": 285227520
                    },
                    "151": {
                        "descriptor": "TEMP SLOT 033",
                        "status": "OK, Swapped",
                        "value": "38C",
                        "value_raw": 285227520
                    },
                    "152": {
                        "descriptor": "TEMP SLOT 034",
                        "status": "OK, Swapped",
                        "value": "36C",
                        "value_raw": 285227008
                    },
                    "153": {
                        "descriptor": "TEMP SLOT 035",
                        "status": "OK, Swapped",
                        "value": "36C",
                        "value_raw": 285227008
                    },
                    "154": {
                        "descriptor": "TEMP SLOT 036",
                        "status": "OK, Swapped",
                        "value": "38C",
                        "value_raw": 285227520
                    },
                    "155": {
                        "descriptor": "TEMP SLOT 037",
                        "status": "OK, Swapped",
                        "value": "38C",
                        "value_raw": 285227520
                    },
                    "156": {
                        "descriptor": "TEMP SLOT 038",
                        "status": "OK, Swapped",
                        "value": "38C",
                        "value_raw": 285227520
                    },
                    "157": {
                        "descriptor": "TEMP SLOT 039",
                        "status": "OK, Swapped",
                        "value": "38C",
                        "value_raw": 285227520
                    },
                    "158": {
                        "descriptor": "TEMP SLOT 040",
                        "status": "OK, Swapped",
                        "value": "38C",
                        "value_raw": 285227520
                    },
                    "159": {
                        "descriptor": "TEMP SLOT 041",
                        "status": "OK, Swapped",
                        "value": "36C",
                        "value_raw": 285227008
                    },
                    "160": {
                        "descriptor": "TEMP SLOT 042",
                        "status": "OK, Swapped",
                        "value": "37C",
                        "value_raw": 285227264
                    },
                    "161": {
                        "descriptor": "TEMP SLOT 043",
                        "status": "OK, Swapped",
                        "value": "42C",
                        "value_raw": 285228544
                    },
                    "162": {
                        "descriptor": "TEMP SLOT 044",
                        "status": "OK, Swapped",
                        "value": "43C",
                        "value_raw": 285228800
                    },
                    "163": {
                        "descriptor": "TEMP SLOT 045",
                        "status": "OK, Swapped",
                        "value": "44C",
                        "value_raw": 285229056
                    },
                    "164": {
                        "descriptor": "TEMP SLOT 046",
                        "status": "OK, Swapped",
                        "value": "43C",
                        "value_raw": 285228800
                    },
                    "165": {
                        "descriptor": "TEMP SLOT 047",
                        "status": "OK, Swapped",
                        "value": "40C",
                        "value_raw": 285228032
                    },
                    "166": {
                        "descriptor": "TEMP SLOT 048",
                        "status": "OK, Swapped",
                        "value": "41C",
                        "value_raw": 285228288
                    },
                    "167": {
                        "descriptor": "TEMP SLOT 049",
                        "status": "OK, Swapped",
                        "value": "43C",
                        "value_raw": 285228800
                    },
                    "168": {
                        "descriptor": "TEMP SLOT 050",
                        "status": "OK, Swapped",
                        "value": "43C",
                        "value_raw": 285228800
                    },
                    "169": {
                        "descriptor": "TEMP SLOT 051",
                        "status": "OK, Swapped",
                        "value": "43C",
                        "value_raw": 285228800
                    },
                    "170": {
                        "descriptor": "TEMP SLOT 052",
                        "status": "OK, Swapped",
                        "value": "41C",
                        "value_raw": 285228288
                    },
                    "171": {
                        "descriptor": "TEMP SLOT 053",
                        "status": "OK, Swapped",
                        "value": "37C",
                        "value_raw": 285227264
                    },
                    "172": {
                        "descriptor": "TEMP SLOT 054",
                        "status": "OK, Swapped",
                        "value": "39C",
                        "value_raw": 285227776
                    },
                    "173": {
                        "descriptor": "TEMP SLOT 055",
                        "status": "OK, Swapped",
                        "value": "40C",
                        "value_raw": 285228032
                    },
                    "174": {
                        "descriptor": "TEMP SLOT 056",
                        "status": "OK, Swapped",
                        "value": "39C",
                        "value_raw": 285227776
                    },
                    "175": {
                        "descriptor": "TEMP SLOT 057",
                        "status": "OK, Swapped",
                        "value": "39C",
                        "value_raw": 285227776
                    },
                    "176": {
                        "descriptor": "TEMP SLOT 058",
                        "status": "OK, Swapped",
                        "value": "37C",
                        "value_raw": 285227264
                    },
                    "177": {
                        "descriptor": "TEMP SLOT 059",
                        "status": "OK, Swapped",
                        "value": "35C",
                        "value_raw": 285226752
                    },
                    "178": {
                        "descriptor": "TEMP SLOT 060",
                        "status": "OK, Swapped",
                        "value": "33C",
                        "value_raw": 285226240
                    },
                    "179": {
                        "descriptor": "TEMP SLOT 061",
                        "status": "OK, Swapped",
                        "value": "36C",
                        "value_raw": 285227008
                    },
                    "180": {
                        "descriptor": "TEMP SLOT 062",
                        "status": "OK, Swapped",
                        "value": "38C",
                        "value_raw": 285227520
                    },
                    "181": {
                        "descriptor": "TEMP SLOT 063",
                        "status": "OK, Swapped",
                        "value": "39C",
                        "value_raw": 285227776
                    },
                    "182": {
                        "descriptor": "TEMP SLOT 064",
                        "status": "OK, Swapped",
                        "value": "39C",
                        "value_raw": 285227776
                    },
                    "183": {
                        "descriptor": "TEMP SLOT 065",
                        "status": "OK, Swapped",
                        "value": "39C",
                        "value_raw": 285227776
                    },
                    "184": {
                        "descriptor": "TEMP SLOT 066",
                        "status": "OK",
                        "value": "43C",
                        "value_raw": 16793344
                    },
                    "185": {
                        "descriptor": "TEMP SLOT 067",
                        "status": "OK, Swapped",
                        "value": "45C",
                        "value_raw": 285229312
                    },
                    "186": {
                        "descriptor": "TEMP SLOT 068",
                        "status": "OK, Swapped",
                        "value": "46C",
                        "value_raw": 285229568
                    },
                    "187": {
                        "descriptor": "TEMP SLOT 069",
                        "status": "OK, Swapped",
                        "value": "46C",
                        "value_raw": 285229568
                    },
                    "188": {
                        "descriptor": "TEMP SLOT 070",
                        "status": "OK, Swapped",
                        "value": "45C",
                        "value_raw": 285229312
                    },
                    "189": {
                        "descriptor": "TEMP SLOT 071",
                        "status": "OK, Swapped",
                        "value": "42C",
                        "value_raw": 285228544
                    },
                    "190": {
                        "descriptor": "TEMP SLOT 072",
                        "status": "OK, Swapped",
                        "value": "40C",
                        "value_raw": 285228032
                    },
                    "191": {
                        "descriptor": "TEMP SLOT 073",
                        "status": "OK, Swapped",
                        "value": "43C",
                        "value_raw": 285228800
                    },
                    "192": {
                        "descriptor": "TEMP SLOT 074",
                        "status": "OK, Swapped",
                        "value": "44C",
                        "value_raw": 285229056
                    },
                    "193": {
                        "descriptor": "TEMP SLOT 075",
                        "status": "OK, Swapped",
                        "value": "45C",
                        "value_raw": 285229312
                    },
                    "194": {
                        "descriptor": "TEMP SLOT 076",
                        "status": "OK, Swapped",
                        "value": "44C",
                        "value_raw": 285229056
                    },
                    "195": {
                        "descriptor": "TEMP SLOT 077",
                        "status": "OK, Swapped",
                        "value": "42C",
                        "value_raw": 285228544
                    },
                    "196": {
                        "descriptor": "TEMP SLOT 078",
                        "status": "OK, Swapped",
                        "value": "45C",
                        "value_raw": 285229312
                    },
                    "197": {
                        "descriptor": "TEMP SLOT 079",
                        "status": "OK, Swapped",
                        "value": "49C",
                        "value_raw": 285230336
                    },
                    "198": {
                        "descriptor": "TEMP SLOT 080",
                        "status": "OK, Swapped",
                        "value": "50C",
                        "value_raw": 285230592
                    },
                    "199": {
                        "descriptor": "TEMP SLOT 081",
                        "status": "OK, Swapped",
                        "value": "51C",
                        "value_raw": 285230848
                    },
                    "200": {
                        "descriptor": "TEMP SLOT 082",
                        "status": "OK, Swapped",
                        "value": "50C",
                        "value_raw": 285230592
                    },
                    "201": {
                        "descriptor": "TEMP SLOT 083",
                        "status": "OK, Swapped",
                        "value": "47C",
                        "value_raw": 285229824
                    },
                    "202": {
                        "descriptor": "TEMP SLOT 084",
                        "status": "OK, Swapped",
                        "value": "45C",
                        "value_raw": 285229312
                    },
                    "203": {
                        "descriptor": "TEMP SLOT 085",
                        "status": "OK, Swapped",
                        "value": "48C",
                        "value_raw": 285230080
                    },
                    "204": {
                        "descriptor": "TEMP SLOT 086",
                        "status": "OK, Swapped",
                        "value": "49C",
                        "value_raw": 285230336
                    },
                    "205": {
                        "descriptor": "TEMP SLOT 087",
                        "status": "OK, Swapped",
                        "value": "49C",
                        "value_raw": 285230336
                    },
                    "206": {
                        "descriptor": "TEMP SLOT 088",
                        "status": "OK, Swapped",
                        "value": "47C",
                        "value_raw": 285229824
                    },
                    "207": {
                        "descriptor": "TEMP SLOT 089",
                        "status": "OK, Swapped",
                        "value": "44C",
                        "value_raw": 285229056
                    },
                    "208": {
                        "descriptor": "TEMP SLOT 090",
                        "status": "OK, Swapped",
                        "value": "43C",
                        "value_raw": 285228800
                    },
                    "209": {
                        "descriptor": "TEMP SLOT 091",
                        "status": "OK, Swapped",
                        "value": "47C",
                        "value_raw": 285229824
                    },
                    "210": {
                        "descriptor": "TEMP SLOT 092",
                        "status": "OK, Swapped",
                        "value": "49C",
                        "value_raw": 285230336
                    },
                    "211": {
                        "descriptor": "TEMP SLOT 093",
                        "status": "OK, Swapped",
                        "value": "50C",
                        "value_raw": 285230592
                    },
                    "212": {
                        "descriptor": "TEMP SLOT 094",
                        "status": "OK",
                        "value": "50C",
                        "value_raw": 16795136
                    },
                    "213": {
                        "descriptor": "TEMP SLOT 095",
                        "status": "OK, Swapped",
                        "value": "48C",
                        "value_raw": 285230080
                    },
                    "214": {
                        "descriptor": "TEMP SLOT 096",
                        "status": "OK, Swapped",
                        "value": "45C",
                        "value_raw": 285229312
                    },
                    "215": {
                        "descriptor": "TEMP SLOT 097",
                        "status": "OK, Swapped",
                        "value": "48C",
                        "value_raw": 285230080
                    },
                    "216": {
                        "descriptor": "TEMP SLOT 098",
                        "status": "OK, Swapped",
                        "value": "49C",
                        "value_raw": 285230336
                    },
                    "217": {
                        "descriptor": "TEMP SLOT 099",
                        "status": "OK, Swapped",
                        "value": "47C",
                        "value_raw": 285229824
                    },
                    "218": {
                        "descriptor": "TEMP SLOT 100",
                        "status": "OK, Swapped",
                        "value": "46C",
                        "value_raw": 285229568
                    },
                    "219": {
                        "descriptor": "TEMP SLOT 101",
                        "status": "OK, Swapped",
                        "value": "43C",
                        "value_raw": 285228800
                    },
                    "220": {
                        "descriptor": "TEMP IOM A",
                        "status": "OK",
                        "value": "50C",
                        "value_raw": 16795136
                    },
                    "221": {
                        "descriptor": "TEMP IOM B",
                        "status": "OK",
                        "value": "53C",
                        "value_raw": 16795904
                    },
                    "222": {
                        "descriptor": "TEMP BB 60 1",
                        "status": "OK",
                        "value": "28C",
                        "value_raw": 16789504
                    },
                    "223": {
                        "descriptor": "TEMP BB 60 2",
                        "status": "OK",
                        "value": "28C",
                        "value_raw": 16789504
                    },
                    "224": {
                        "descriptor": "TEMP BB 42 1",
                        "status": "OK",
                        "value": "18C",
                        "value_raw": 16786944
                    },
                    "225": {
                        "descriptor": "TEMP BB 42 2",
                        "status": "OK",
                        "value": "18C",
                        "value_raw": 16786944
                    },
                    "226": {
                        "descriptor": "TEMP PRI A DIE",
                        "status": "OK",
                        "value": "57C",
                        "value_raw": 16796928
                    },
                    "227": {
                        "descriptor": "TEMP SEC1 A DIE",
                        "status": "OK",
                        "value": "80C",
                        "value_raw": 16802816
                    },
                    "228": {
                        "descriptor": "TEMP SEC2 A DIE",
                        "status": "OK",
                        "value": "62C",
                        "value_raw": 16798208
                    },
                    "229": {
                        "descriptor": "TEMP PRI A MEM",
                        "status": "OK",
                        "value": "47C",
                        "value_raw": 16794368
                    },
                    "230": {
                        "descriptor": "TEMP SEC1 A MEM",
                        "status": "OK",
                        "value": "47C",
                        "value_raw": 16794368
                    },
                    "231": {
                        "descriptor": "TEMP SEC2 A MEM",
                        "status": "OK",
                        "value": "41C",
                        "value_raw": 16792832
                    },
                    "232": {
                        "descriptor": "TEMP PRI B DIE",
                        "status": "OK",
                        "value": "60C",
                        "value_raw": 16797696
                    },
                    "233": {
                        "descriptor": "TEMP SEC1 B DIE",
                        "status": "OK",
                        "value": "82C",
                        "value_raw": 16803328
                    },
                    "234": {
                        "descriptor": "TEMP SEC2 B DIE",
                        "status": "OK",
                        "value": "71C",
                        "value_raw": 16800512
                    },
                    "235": {
                        "descriptor": "TEMP PRI B MEM",
                        "status": "OK",
                        "value": "49C",
                        "value_raw": 16794880
                    },
                    "236": {
                        "descriptor": "TEMP SEC1 B MEM",
                        "status": "OK",
                        "value": "52C",
                        "value_raw": 16795648
                    },
                    "237": {
                        "descriptor": "TEMP SEC2 B MEM",
                        "status": "OK",
                        "value": "42C",
                        "value_raw": 16793088
                    },
                    "238": {
                        "descriptor": "TEMP IOM A 5V",
                        "status": "OK",
                        "value": "48C",
                        "value_raw": 16794624
                    },
                    "239": {
                        "descriptor": "TEMP IOM B 5V",
                        "status": "OK",
                        "value": "54C",
                        "value_raw": 16796160
                    },
                    "240": {
                        "descriptor": "TEMP PSU A AMB",
                        "status": "OK",
                        "value": "37C",
                        "value_raw": 16791808
                    },
                    "241": {
                        "descriptor": "TEMP PSU A HOT",
                        "status": "OK",
                        "value": "48C",
                        "value_raw": 16794624
                    },
                    "242": {
                        "descriptor": "TEMP PSU A PRI",
                        "status": "OK",
                        "value": "43C",
                        "value_raw": 16793344
                    },
                    "243": {
                        "descriptor": "TEMP PSU B AMB",
                        "status": "OK",
                        "value": "35C",
                        "value_raw": 16791296
                    },
                    "244": {
                        "descriptor": "TEMP PSU B HOT",
                        "status": "OK",
                        "value": "49C",
                        "value_raw": 16794880
                    },
                    "245": {
                        "descriptor": "TEMP PSU B PRI",
                        "status": "OK",
                        "value": "43C",
                        "value_raw": 16793344
                    }
                },
                "Enclosure Services Controller Electronics": {
                    "247": {
                        "descriptor": "ESCE IOMA,1EA0484-C1          ,THCCT03821EG014F    ,5000CCAB0511683C,,00:0C:CA:07:45:77,3.1.11",
                        "status": "OK",
                        "value": None,
                        "value_raw": 17826176
                    },
                    "248": {
                        "descriptor": "ESCE IOMB,1EA0484-C1          ,THCCT03821EG0150    ,5000CCAB0511687C,,00:0C:CA:07:45:6F,3.1.11",
                        "status": "OK",
                        "value": None,
                        "value_raw": 17825920
                    }
                },
                "SAS Expander": {
                    "250": {
                        "descriptor": "EXP IOMA 0,3010-007,5000CCAB0511683D",
                        "status": "OK",
                        "value": None,
                        "value_raw": 16777216
                    },
                    "251": {
                        "descriptor": "EXP IOMA 1,3010-007,5000CCAB0511683F",
                        "status": "OK",
                        "value": None,
                        "value_raw": 16777216
                    },
                    "252": {
                        "descriptor": "EXP IOMA 2,3010-007,5000CCAB0511687F",
                        "status": "OK",
                        "value": None,
                        "value_raw": 16777216
                    },
                    "253": {
                        "descriptor": "EXP IOMB 0,3010-007,5000CCAB0511687D",
                        "status": "OK",
                        "value": None,
                        "value_raw": 16777216
                    },
                    "254": {
                        "descriptor": "EXP IOMB 1,3010-007,5000CCAB05116879",
                        "status": "OK",
                        "value": None,
                        "value_raw": 16777216
                    },
                    "255": {
                        "descriptor": "EXP IOMB 2,3010-007,5000CCAB0511687B",
                        "status": "OK",
                        "value": None,
                        "value_raw": 16777216
                    }
                },
                "SAS Connector": {
                    "257": {
                        "descriptor": "CONN HOST 00",
                        "status": "OK",
                        "value": "Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]",
                        "value_raw": 17170304
                    },
                    "258": {
                        "descriptor": "CONN HOST 01",
                        "status": "Not installed",
                        "value": "Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]",
                        "value_raw": 84279040
                    },
                    "259": {
                        "descriptor": "CONN HOST 02",
                        "status": "Not installed",
                        "value": "Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]",
                        "value_raw": 84279040
                    },
                    "260": {
                        "descriptor": "CONN HOST 03",
                        "status": "Not installed",
                        "value": "Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]",
                        "value_raw": 84279040
                    },
                    "261": {
                        "descriptor": "CONN HOST 04",
                        "status": "Not installed",
                        "value": "Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]",
                        "value_raw": 84279040
                    },
                    "262": {
                        "descriptor": "CONN HOST 05",
                        "status": "Not installed",
                        "value": "Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]",
                        "value_raw": 84279040
                    },
                    "263": {
                        "descriptor": "CONN HOST 06",
                        "status": "OK",
                        "value": "Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]",
                        "value_raw": 17170304
                    },
                    "264": {
                        "descriptor": "CONN HOST 07",
                        "status": "Not installed",
                        "value": "Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]",
                        "value_raw": 84279040
                    },
                    "265": {
                        "descriptor": "CONN HOST 08",
                        "status": "Not installed",
                        "value": "Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]",
                        "value_raw": 84279040
                    },
                    "266": {
                        "descriptor": "CONN HOST 09",
                        "status": "Not installed",
                        "value": "Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]",
                        "value_raw": 84279040
                    },
                    "267": {
                        "descriptor": "CONN HOST 10",
                        "status": "Not installed",
                        "value": "Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]",
                        "value_raw": 84279040
                    },
                    "268": {
                        "descriptor": "CONN HOST 11",
                        "status": "Not installed",
                        "value": "Mini SAS HD 4x receptacle (SFF-8644) [max 4 phys]",
                        "value_raw": 84279040
                    }
                },
                "Voltage Sensor": {
                    "270": {
                        "descriptor": "VOLT PSU A AC",
                        "status": "OK",
                        "value": "200.0V",
                        "value_raw": 16797216
                    },
                    "271": {
                        "descriptor": "VOLT PSU A 12V",
                        "status": "OK",
                        "value": "12.24V",
                        "value_raw": 16778440
                    },
                    "272": {
                        "descriptor": "VOLT PSU B AC",
                        "status": "OK",
                        "value": "201.0V",
                        "value_raw": 16797316
                    },
                    "273": {
                        "descriptor": "VOLT PSU B 12V",
                        "status": "OK",
                        "value": "12.28V",
                        "value_raw": 16778444
                    },
                    "274": {
                        "descriptor": "VOLT IOM A 5V",
                        "status": "OK",
                        "value": "5.03V",
                        "value_raw": 16777719
                    },
                    "275": {
                        "descriptor": "VOLT IOM A 12V",
                        "status": "OK",
                        "value": "12.0V",
                        "value_raw": 16778416
                    },
                    "276": {
                        "descriptor": "VOLT IOM B 5V",
                        "status": "OK",
                        "value": "5.03V",
                        "value_raw": 16777719
                    },
                    "277": {
                        "descriptor": "VOLT IOM B 12V",
                        "status": "OK",
                        "value": "12.0V",
                        "value_raw": 16778416
                    }
                },
                "Current Sensor": {
                    "279": {
                        "descriptor": "CURR PSU A IN",
                        "status": "OK",
                        "value": "2.18A",
                        "value_raw": 16777434
                    },
                    "280": {
                        "descriptor": "CURR PSU A OUT",
                        "status": "OK",
                        "value": "32.13A",
                        "value_raw": 16780429
                    },
                    "281": {
                        "descriptor": "CURR PSU B IN",
                        "status": "OK",
                        "value": "2.21A",
                        "value_raw": 16777437
                    },
                    "282": {
                        "descriptor": "CURR PSU B OUT",
                        "status": "OK",
                        "value": "32.5A",
                        "value_raw": 16780466
                    },
                    "283": {
                        "descriptor": "CURR IOM A 12V",
                        "status": "OK",
                        "value": "14.07A",
                        "value_raw": 16778623
                    },
                    "284": {
                        "descriptor": "CURR IOM A 5V",
                        "status": "OK",
                        "value": "20.25A",
                        "value_raw": 16779241
                    },
                    "285": {
                        "descriptor": "CURR IOM B 12V",
                        "status": "OK",
                        "value": "14.95A",
                        "value_raw": 16778711
                    },
                    "286": {
                        "descriptor": "CURR IOM B 5V",
                        "status": "OK",
                        "value": "20.75A",
                        "value_raw": 16779291
                    }
                },
                "Door Lock": {
                    "288": {
                        "descriptor": "ENCLOSURE COVER",
                        "status": "OK",
                        "value": None,
                        "value_raw": 16777216
                    }
                }
            }
        },
        {  # ES102 JBOD sysfs output (for mocking)
            "91": "sdasl",
            "13": "sdatj",
            "65": "sdarl",
            "17": "sdatn",
            "101": "sdasv",
            "37": "sdauh",
            "64": "sdark",
            "46": "sdauo",
            "10": "sdatg",
            "97": "sdasr",
            "38": "sdaui",
            "79": "sdarz",
            "72": "sdars",
            "48": "sdauq",
            "61": "sdarh",
            "33": "sdaud",
            "84": "sdase",
            "93": "sdasn",
            "59": "sdarf",
            "54": "sdara",
            "68": "sdaro",
            "52": "sdaut",
            "42": "sdaqx",
            "63": "sdarj",
            "26": "sdatw",
            "98": "sdass",
            "22": "sdats",
            "92": "sdasm",
            "82": "sdasc",
            "36": "sdaug",
            "12": "sdati",
            "24": "sdatu",
            "7": "sdatd",
            "3": "sdasz",
            "69": "sdarp",
            "88": "sdasi",
            "100": "sdasu",
            "23": "sdatt",
            "78": "sdary",
            "28": "sdaty",
            "67": "sdarn",
            "21": "sdatr",
            "9": "sdatf",
            "80": "sdasa",
            "2": "sdasy",
            "30": "sdaua",
            "57": "sdard",
            "25": "sdatv",
            "90": "sdask",
            "32": "sdauc",
            "58": "sdare",
            "75": "sdarv",
            "86": "sdash",
            "15": "sdatl",
            "89": "sdasj",
            "95": "sdasp",
            "8": "sdate",
            "76": "sdarw",
            "14": "sdatk",
            "16": "sdatm",
            "40": "sdauk",
            "53": "sdaqz",
            "35": "sdauf",
            "29": "sdatz",
            "6": "sdatc",
            "94": "sdaso",
            "19": "sdatp",
            "55": "sdarb",
            "43": "sdaum",
            "39": "sdauj",
            "96": "sdasq",
            "51": "sdaus",
            "77": "sdarx",
            "34": "sdaue",
            "11": "sdath",
            "71": "sdarr",
            "18": "sdato",
            "73": "sdart",
            "85": "sdasf",
            "44": "sdaqy",
            "66": "sdarm",
            "81": "sdasb",
            "31": "sdaub",
            "60": "sdarg",
            "56": "sdarc",
            "1": "sdasx",
            "83": "sdasd",
            "0": "sdasw",
            "87": "sdasg",
            "62": "sdari",
            "4": "sdata",
            "5": "sdatb",
            "41": "sdaul",
            "50": "sdaur",
            "20": "sdatq",
            "47": "sdaup",
            "74": "sdaru",
            "99": "sdast",
            "45": "sdaun",
            "70": "sdarq",
            "27": "sdatx",
            "49": "sdauu"
        }
    )
])
def test_enclosure_class(data):
    raw, formatted, sysfs_disks = data
    with patch('middlewared.plugins.enclosure_.enclosure_class.inquiry') as inquiry:
        inquiry.return_value = {
            'vendor': formatted['vendor'],
            'product': formatted['product'],
            'revision': formatted['revision'],
        }
        with patch('middlewared.plugins.enclosure_.enclosure_class.map_disks_to_enclosure_slots') as map_disks_to_enclosure_slots:
            map_disks_to_enclosure_slots.return_value = sysfs_disks

            enc = Enclosure(
                formatted['bsg'],
                formatted['sg'],
                formatted['dmi'],
                raw,
            )
            assert enc.asdict() == formatted
