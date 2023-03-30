import contextlib
import pytest

from unittest.mock import patch

from middlewared.plugins.ports.ports import PortService, ValidationErrors
from middlewared.pytest.unit.middleware import Middleware


PORTS_IN_USE = [
    {
        'namespace': 'snmp',
        'title': 'SNMP Service',
        'ports': [
            [
                '0.0.0.0',
                160
            ],
            [
                '0.0.0.0',
                161
            ]
        ],
        'port_details': [
            {
                'description': None,
                'ports': [
                    [
                        '0.0.0.0',
                        160
                    ],
                    [
                        '0.0.0.0',
                        161
                    ]
                ]
            }
        ]
    },
    {
        'namespace': 'ssh',
        'title': 'SSH Service',
        'ports': [
            [
                '0.0.0.0',
                22
            ]
        ],
        'port_details': [
            {
                'description': None,
                'ports': [
                    [
                        '0.0.0.0',
                        22
                    ]
                ]
            }
        ]
    },
    {
        'namespace': 'tftp',
        'title': 'TFTP Service',
        'ports': [
            [
                '0.0.0.0',
                69
            ]
        ],
        'port_details': [
            {
                'description': None,
                'ports': [
                    [
                        '0.0.0.0',
                        69
                    ]
                ]
            }
        ]
    },
    {
        'namespace': 'chart.release',
        'title': 'Applications',
        'ports': [
            [
                '0.0.0.0',
                21027
            ],
            [
                '0.0.0.0',
                22000
            ],
            [
                '0.0.0.0',
                22000
            ],
            [
                '0.0.0.0',
                8384
            ],
            [
                '0.0.0.0',
                32400
            ],
            [
                '0.0.0.0',
                22601
            ],
            [
                '0.0.0.0',
                59372
            ],
            [
                '0.0.0.0',
                14831
            ],
            [
                '0.0.0.0',
                20489
            ],
            [
                '::',
                21028
            ],
        ],
        'port_details': [
            {
                'description': '\'syncthing\' application',
                'ports': [
                    [
                        '0.0.0.0',
                        21027
                    ],
                    [
                        '0.0.0.0',
                        22000
                    ],
                    [
                        '0.0.0.0',
                        22000
                    ],
                    [
                        '0.0.0.0',
                        8384
                    ],
                    [
                        '::',
                        21028
                    ],
                ]
            },
            {
                'description': '\'plex\' application',
                'ports': [
                    [
                        '0.0.0.0',
                        32400
                    ],
                    [
                        '0.0.0.0',
                        22601
                    ],
                    [
                        '0.0.0.0',
                        59372
                    ],
                    [
                        '0.0.0.0',
                        14831
                    ]
                ]
            },
            {
                'description': '\'netdata\' application',
                'ports': [
                    [
                        '0.0.0.0',
                        20489
                    ]
                ]
            },
        ]
    },
    {
        'namespace': 'kmip',
        'title': 'KMIP Service',
        'ports': [
            [
                '0.0.0.0',
                5696
            ]
        ],
        'port_details': [
            {
                'description': None,
                'ports': [
                    [
                        '0.0.0.0',
                        5696
                    ]
                ]
            }
        ]
    },
    {
        'namespace': 'rsyncd',
        'title': 'Rsyncd Service',
        'ports': [
            [
                '0.0.0.0',
                11000
            ]
        ],
        'port_details': [
            {
                'description': None,
                'ports': [
                    [
                        '0.0.0.0',
                        11000
                    ]
                ]
            }
        ]
    },
    {
        'namespace': 'webdav',
        'title': 'Webdav Service',
        'ports': [
            [
                '0.0.0.0',
                10258
            ],
            [
                '0.0.0.0',
                14658
            ]
        ],
        'port_details': [
            {
                'description': None,
                'ports': [
                    [
                        '0.0.0.0',
                        10258
                    ],
                    [
                        '0.0.0.0',
                        14658
                    ]
                ]
            }
        ]
    },
    {
        'namespace': 'smb',
        'title': 'SMB Service',
        'ports': [
            [
                '0.0.0.0',
                137
            ],
            [
                '0.0.0.0',
                138
            ],
            [
                '0.0.0.0',
                139
            ],
            [
                '0.0.0.0',
                445
            ]
        ],
        'port_details': [
            {
                'description': None,
                'ports': [
                    [
                        '0.0.0.0',
                        137
                    ],
                    [
                        '0.0.0.0',
                        138
                    ],
                    [
                        '0.0.0.0',
                        139
                    ],
                    [
                        '0.0.0.0',
                        445
                    ]
                ]
            }
        ]
    },
    {
        'namespace': 's3',
        'title': 'S3 Service',
        'ports': [
            [
                '192.168.0.70',
                8703
            ],
            [
                '192.168.0.70',
                9010
            ],
            [
                '2001:db8:3333:4444:5555:6666:7777:8888',
                8704
            ]
        ],
        'port_details': [
            {
                'description': None,
                'ports': [
                    [
                        '192.168.0.70',
                        8703
                    ],
                    [
                        '192.168.0.70',
                        9010
                    ],
                    [
                        '2001:db8:3333:4444:5555:6666:7777:8888',
                        8704
                    ]
                ]
            }
        ]
    },
    {
        'namespace': 'kubernetes',
        'title': 'Kubernetes Service',
        'ports': [
            [
                '0.0.0.0',
                6443
            ]
        ],
        'port_details': [
            {
                'description': None,
                'ports': [
                    [
                        '0.0.0.0',
                        6443
                    ]
                ]
            }
        ]
    },
    {
        'namespace': 'ftp',
        'title': 'FTP Service',
        'ports': [
            [
                '0.0.0.0',
                3730
            ]
        ],
        'port_details': [
            {
                'description': None,
                'ports': [
                    [
                        '0.0.0.0',
                        3730
                    ]
                ]
            }
        ]
    },
    {
        'namespace': 'openvpn.server',
        'title': 'Openvpn Server Service',
        'ports': [
            [
                '0.0.0.0',
                1194
            ]
        ],
        'port_details': [
            {
                'description': None,
                'ports': [
                    [
                        '0.0.0.0',
                        1194
                    ]
                ]
            }
        ]
    },
    {
        'namespace': 'system.general',
        'title': 'WebUI Service',
        'ports': [
            [
                '0.0.0.0',
                80
            ],
            [
                '0.0.0.0',
                443
            ],
            [
                '::',
                8080
            ],
        ],
        'port_details': [
            {
                'description': None,
                'ports': [
                    [
                        '0.0.0.0',
                        80
                    ],
                    [
                        '0.0.0.0',
                        443
                    ],
                    [
                        '::',
                        8080
                    ],
                ]
            }
        ]
    },
    {
        'namespace': 'reporting',
        'title': 'Reporting Service',
        'ports': [
            [
                '0.0.0.0',
                2003
            ]
        ],
        'port_details': [
            {
                'description': None,
                'ports': [
                    [
                        '0.0.0.0',
                        2003
                    ]
                ]
            }
        ]
    },
    {
        'namespace': 'iscsi.global',
        'title': 'iSCSI Service',
        'ports': [
            [
                '0.0.0.0',
                3260
            ]
        ],
        'port_details': [
            {
                'description': None,
                'ports': [
                    [
                        '0.0.0.0',
                        3260
                    ]
                ]
            }
        ]
    },
    {
        'namespace': 'nfs',
        'title': 'NFS Service',
        'ports': [
            [
                '0.0.0.0',
                2049
            ]
        ],
        'port_details': [
            {
                'description': None,
                'ports': [
                    [
                        '0.0.0.0',
                        2049
                    ]
                ]
            }
        ]
    },
    {
        'namespace': 'gluster.fuse',
        'title': 'Gluster Service',
        'ports': [
            [
                '0.0.0.0',
                24007
            ],
            [
                '0.0.0.0',
                24008
            ],
            [
                '::',
                24008
            ]
        ],
        'port_details': [
            {
                'description': None,
                'ports': [
                    [
                        '0.0.0.0',
                        24007
                    ],
                    [
                        '0.0.0.0',
                        24008
                    ],
                    [
                        '::',
                        24008
                    ]
                ]
            }
        ]
    },
    {
        'title': 'System',
        'ports': [
            [
                '0.0.0.0',
                67
            ],
            [
                '0.0.0.0',
                123
            ],
            [
                '0.0.0.0',
                3702
            ],
            [
                '0.0.0.0',
                5353
            ],
            [
                '0.0.0.0',
                6000
            ],
            [
                '::',
                68
            ]
        ],
        'port_details': [
            {
                'description': None,
                'ports': [
                    [
                        '0.0.0.0',
                        67
                    ],
                    [
                        '::',
                        68
                    ],
                    [
                        '0.0.0.0',
                        123
                    ],
                    [
                        '0.0.0.0',
                        3702
                    ],
                    [
                        '0.0.0.0',
                        5353
                    ],
                    [
                        '0.0.0.0',
                        6000
                    ]
                ]
            }
        ],
        'namespace': 'system'
    }
]


@contextlib.contextmanager
def get_port_service():
    with patch('middlewared.plugins.ports.ports.PortService.get_in_use') as get_in_use_port:
        get_in_use_port.return_value = PORTS_IN_USE
        yield PortService(Middleware())


@pytest.mark.parametrize('port,bindip,whitelist_namespace', [
    (67, '0.0.0.0', 'system'),
    (67, '192.168.0.12', 'system'),
    (24007, '0.0.0.0', 'gluster.fuse'),
    (24007, '192.168.0.12', 'gluster.fuse'),
    (21027, '0.0.0.0', 'chart.release'),
    (21027, '192.168.0.12', 'chart.release'),
])
@pytest.mark.asyncio
async def test_port_validate_whitelist_namespace_logic(port, bindip, whitelist_namespace):
    with get_port_service() as port_service:
        with pytest.raises(ValidationErrors):
            await port_service.validate_port('test', port, bindip, raise_error=True)

        assert (await port_service.validate_port('test', port, bindip, whitelist_namespace)).errors == []


@pytest.mark.parametrize('port,bindip,should_work', [
    (80, '0.0.0.0', False),
    (81, '0.0.0.0', True),
    (8703, '0.0.0.0', False),
    (8703, '192.168.0.70', False),
    (8703, '192.168.0.71', True),
    (9010, '0.0.0.0', False),
    (9010, '192.168.0.70', False),
    (9010, '192.168.0.71', True),
    (6443, '192.168.0.71', False),
])
@pytest.mark.asyncio
async def test_port_validation_logic(port, bindip, should_work):
    with get_port_service() as port_service:
        if should_work:
            assert (await port_service.validate_port('test', port, bindip, raise_error=False)).errors == []
        else:
            with pytest.raises(ValidationErrors):
                await port_service.validate_port('test', port, bindip, raise_error=True)
