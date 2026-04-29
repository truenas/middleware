import contextlib
import errno
from unittest.mock import patch

import pytest

from middlewared.plugins.ports import PortService
from middlewared.pytest.unit.middleware import Middleware
from middlewared.service import ValidationErrors

PORTS_IN_USE = [
    {
        "namespace": "snmp",
        "title": "SNMP Service",
        "ports": [
            [
                "0.0.0.0",
                160
            ],
            [
                "0.0.0.0",
                161
            ]
        ],
        "port_details": [
            {
                "description": None,
                "ports": [
                    [
                        "0.0.0.0",
                        160
                    ],
                    [
                        "0.0.0.0",
                        161
                    ]
                ]
            }
        ]
    },
    {
        "namespace": "ssh",
        "title": "SSH Service",
        "ports": [
            [
                "0.0.0.0",
                22
            ]
        ],
        "port_details": [
            {
                "description": None,
                "ports": [
                    [
                        "0.0.0.0",
                        22
                    ]
                ]
            }
        ]
    },
    {
        "namespace": "tftp",
        "title": "TFTP Service",
        "ports": [
            [
                "0.0.0.0",
                69
            ]
        ],
        "port_details": [
            {
                "description": None,
                "ports": [
                    [
                        "0.0.0.0",
                        69
                    ]
                ]
            }
        ]
    },
    {
        "namespace": "kmip",
        "title": "KMIP Service",
        "ports": [
            [
                "0.0.0.0",
                5696
            ]
        ],
        "port_details": [
            {
                "description": None,
                "ports": [
                    [
                        "0.0.0.0",
                        5696
                    ]
                ]
            }
        ]
    },
    {
        "namespace": "rsyncd",
        "title": "Rsyncd Service",
        "ports": [
            [
                "0.0.0.0",
                11000
            ]
        ],
        "port_details": [
            {
                "description": None,
                "ports": [
                    [
                        "0.0.0.0",
                        11000
                    ]
                ]
            }
        ]
    },
    {
        "namespace": "webdav",
        "title": "Webdav Service",
        "ports": [
            [
                "0.0.0.0",
                10258
            ],
            [
                "0.0.0.0",
                14658
            ]
        ],
        "port_details": [
            {
                "description": None,
                "ports": [
                    [
                        "0.0.0.0",
                        10258
                    ],
                    [
                        "0.0.0.0",
                        14658
                    ]
                ]
            }
        ]
    },
    {
        "namespace": "smb",
        "title": "SMB Service",
        "ports": [
            [
                "0.0.0.0",
                137
            ],
            [
                "0.0.0.0",
                138
            ],
            [
                "0.0.0.0",
                139
            ],
            [
                "0.0.0.0",
                445
            ]
        ],
        "port_details": [
            {
                "description": None,
                "ports": [
                    [
                        "0.0.0.0",
                        137
                    ],
                    [
                        "0.0.0.0",
                        138
                    ],
                    [
                        "0.0.0.0",
                        139
                    ],
                    [
                        "0.0.0.0",
                        445
                    ]
                ]
            }
        ]
    },
    {
        "namespace": "s3",
        "title": "S3 Service",
        "ports": [
            [
                "192.168.0.70",
                8703
            ],
            [
                "192.168.0.70",
                9010
            ],
            [
                "2001:db8:3333:4444:5555:6666:7777:8888",
                8704
            ]
        ],
        "port_details": [
            {
                "description": None,
                "ports": [
                    [
                        "192.168.0.70",
                        8703
                    ],
                    [
                        "192.168.0.70",
                        9010
                    ],
                    [
                        "2001:db8:3333:4444:5555:6666:7777:8888",
                        8704
                    ]
                ]
            }
        ]
    },
    {
        "namespace": "ftp",
        "title": "FTP Service",
        "ports": [
            [
                "0.0.0.0",
                3730
            ]
        ],
        "port_details": [
            {
                "description": None,
                "ports": [
                    [
                        "0.0.0.0",
                        3730
                    ]
                ]
            }
        ]
    },
    {
        "namespace": "openvpn.server",
        "title": "Openvpn Server Service",
        "ports": [
            [
                "0.0.0.0",
                1194
            ]
        ],
        "port_details": [
            {
                "description": None,
                "ports": [
                    [
                        "0.0.0.0",
                        1194
                    ]
                ]
            }
        ]
    },
    {
        "namespace": "system.general",
        "title": "WebUI Service",
        "ports": [
            [
                "0.0.0.0",
                80
            ],
            [
                "0.0.0.0",
                443
            ],
            [
                "::",
                8080
            ],
        ],
        "port_details": [
            {
                "description": None,
                "ports": [
                    [
                        "0.0.0.0",
                        80
                    ],
                    [
                        "0.0.0.0",
                        443
                    ],
                    [
                        "::",
                        8080
                    ],
                ]
            }
        ]
    },
    {
        "namespace": "reporting",
        "title": "Reporting Service",
        "ports": [
            [
                "0.0.0.0",
                2003
            ]
        ],
        "port_details": [
            {
                "description": None,
                "ports": [
                    [
                        "0.0.0.0",
                        2003
                    ]
                ]
            }
        ]
    },
    {
        "namespace": "iscsi.global",
        "title": "iSCSI Service",
        "ports": [
            [
                "0.0.0.0",
                3260
            ]
        ],
        "port_details": [
            {
                "description": None,
                "ports": [
                    [
                        "0.0.0.0",
                        3260
                    ]
                ]
            }
        ]
    },
    {
        "namespace": "nfs",
        "title": "NFS Service",
        "ports": [
            [
                "0.0.0.0",
                2049
            ]
        ],
        "port_details": [
            {
                "description": None,
                "ports": [
                    [
                        "0.0.0.0",
                        2049
                    ]
                ]
            }
        ]
    },
    {
        "namespace": "gluster.fuse",
        "title": "Gluster Service",
        "ports": [
            [
                "0.0.0.0",
                24007
            ],
            [
                "0.0.0.0",
                24008
            ],
            [
                "::",
                24008
            ]
        ],
        "port_details": [
            {
                "description": None,
                "ports": [
                    [
                        "0.0.0.0",
                        24007
                    ],
                    [
                        "0.0.0.0",
                        24008
                    ],
                    [
                        "::",
                        24008
                    ]
                ]
            }
        ]
    },
    {
        "title": "System",
        "ports": [
            [
                "0.0.0.0",
                67
            ],
            [
                "0.0.0.0",
                123
            ],
            [
                "0.0.0.0",
                3702
            ],
            [
                "0.0.0.0",
                5353
            ],
            [
                "0.0.0.0",
                6000
            ],
            [
                "::",
                68
            ]
        ],
        "port_details": [
            {
                "description": None,
                "ports": [
                    [
                        "0.0.0.0",
                        67
                    ],
                    [
                        "::",
                        68
                    ],
                    [
                        "0.0.0.0",
                        123
                    ],
                    [
                        "0.0.0.0",
                        3702
                    ],
                    [
                        "0.0.0.0",
                        5353
                    ],
                    [
                        "0.0.0.0",
                        6000
                    ]
                ]
            }
        ],
        "namespace": "system"
    }
]


@contextlib.contextmanager
def get_port_service():
    with patch("middlewared.plugins.ports.ports.get_in_use") as get_in_use_port:
        get_in_use_port.return_value = PORTS_IN_USE
        yield PortService(Middleware())


@pytest.mark.parametrize("port,bindip,whitelist_namespace", [
    (67, "0.0.0.0", "system"),
    (67, "192.168.0.12", "system"),
    (24007, "0.0.0.0", "gluster.fuse"),
    (24007, "192.168.0.12", "gluster.fuse"),
    (68, "::", "system"),
    (68, "2001:db8:3333:4444:5555:6666:7777:8888", "system"),
    (24008, "::", "gluster.fuse"),
    (24008, "2001:db8:3333:4444:5555:6666:7777:8888", "gluster.fuse"),
])
@pytest.mark.asyncio
async def test_port_validate_whitelist_namespace_logic(port, bindip, whitelist_namespace):
    with get_port_service() as port_service:
        with pytest.raises(ValidationErrors):
            await port_service.validate_port("test", port, bindip, raise_error=True)

        assert (await port_service.validate_port("test", port, bindip, whitelist_namespace)).errors == []


@pytest.mark.parametrize("port,bindip,should_work", [
    (80, "0.0.0.0", False),
    (81, "0.0.0.0", True),
    (8703, "0.0.0.0", False),
    (8703, "192.168.0.70", False),
    (8703, "192.168.0.71", True),
    (9010, "0.0.0.0", False),
    (9010, "192.168.0.70", False),
    (9010, "192.168.0.71", True),
    (80, "::", True),
    (8080, "::", False),
    (8081, "::", True),
    (8703, "::", True),
    (8704, "::", False),
    (8704, "2001:db8:3333:4444:5555:6666:7777:8888", False),
    (8704, "2001:db8:3333:4444:5555:6666:7777:8889", True),
])
@pytest.mark.asyncio
async def test_port_validation_logic(port, bindip, should_work):
    with get_port_service() as port_service:
        if should_work:
            assert (await port_service.validate_port("test", port, bindip, raise_error=False)).errors == []
        else:
            with pytest.raises(ValidationErrors):
                await port_service.validate_port("test", port, bindip, raise_error=True)


@pytest.mark.asyncio
async def test_batch_validate_ports_no_conflicts():
    with get_port_service() as port_service:
        result = await port_service.validate_ports(
            "test", [{"port": 81, "bindip": "0.0.0.0"}, {"port": 82, "bindip": "0.0.0.0"}]
        )
        assert result == []


@pytest.mark.asyncio
async def test_batch_validate_ports_some_conflicts():
    with get_port_service() as port_service:
        result = await port_service.validate_ports(
            "test", [{"port": 80, "bindip": "0.0.0.0"}, {"port": 81, "bindip": "0.0.0.0"}]
        )
        assert len(result) == 1
        assert result[0][0] == "test"
        assert "80" in result[0][1]


@pytest.mark.asyncio
async def test_batch_validate_ports_all_conflicts():
    with get_port_service() as port_service:
        result = await port_service.validate_ports(
            "test", [{"port": 80, "bindip": "0.0.0.0"}, {"port": 22, "bindip": "0.0.0.0"}]
        )
        assert len(result) == 2


@pytest.mark.asyncio
async def test_batch_validate_ports_raise_error():
    with get_port_service() as port_service:
        with pytest.raises(ValidationErrors) as exc_info:
            await port_service.validate_ports(
                "test",
                [{"port": 80, "bindip": "0.0.0.0"}, {"port": 22, "bindip": "0.0.0.0"}],
                raise_error=True,
            )
        errors = list(exc_info.value)
        assert len(errors) == 2


@pytest.mark.asyncio
async def test_batch_validate_ports_raise_error_no_conflicts():
    with get_port_service() as port_service:
        result = await port_service.validate_ports(
            "test",
            [{"port": 81, "bindip": "0.0.0.0"}],
            raise_error=True,
        )
        assert result is None


@pytest.mark.asyncio
async def test_batch_validate_ports_whitelist_namespace():
    with get_port_service() as port_service:
        result = await port_service.validate_ports(
            "test",
            [{"port": 80, "bindip": "0.0.0.0"}],
            whitelist_namespace="system.general",
        )
        assert result == []


@pytest.mark.asyncio
async def test_batch_validate_ports_default_bindip():
    with get_port_service() as port_service:
        result = await port_service.validate_ports("test", [{"port": 80}])
        assert len(result) == 1


@pytest.mark.asyncio
async def test_batch_validate_ports_empty_list():
    with get_port_service() as port_service:
        assert await port_service.validate_ports("test", []) == []
        assert await port_service.validate_ports("test", [], raise_error=True) is None


@pytest.mark.asyncio
async def test_batch_validate_ports_mixed_ip_versions():
    with get_port_service() as port_service:
        result = await port_service.validate_ports(
            "test",
            [
                {"port": 80, "bindip": "0.0.0.0"},   # Conflicts (WebUI on IPv4)
                {"port": 80, "bindip": "::"},          # No conflict (WebUI not on ::)
                {"port": 8080, "bindip": "::"},        # Conflicts (WebUI on ::)
            ],
        )
        assert len(result) == 2


@pytest.mark.asyncio
async def test_batch_validate_ports_serialized_tuple_structure():
    """Each entry in the serialized result must be a (schema, errmsg, errno) tuple."""
    with get_port_service() as port_service:
        result = await port_service.validate_ports(
            "my.schema", [{"port": 80, "bindip": "0.0.0.0"}]
        )
        assert len(result) == 1
        attr, errmsg, err_no = result[0]
        assert attr == "my.schema"
        assert isinstance(errmsg, str)
        assert err_no == errno.EINVAL


@pytest.mark.asyncio
async def test_batch_validate_ports_serialized_error_message_content():
    """Serialized error message should contain the port, IP, and service title."""
    with get_port_service() as port_service:
        result = await port_service.validate_ports(
            "test", [{"port": 80, "bindip": "0.0.0.0"}]
        )
        errmsg = result[0][1]
        assert "The port is being used by following services:" in errmsg
        assert '"0.0.0.0:80"' in errmsg
        assert "WebUI Service" in errmsg


@pytest.mark.asyncio
async def test_batch_validate_ports_serialized_multiple_errors():
    """Multiple conflicts should each produce a separate serialized entry with correct content."""
    with get_port_service() as port_service:
        result = await port_service.validate_ports(
            "app.schema",
            [
                {"port": 80, "bindip": "0.0.0.0"},
                {"port": 22, "bindip": "0.0.0.0"},
                {"port": 59999, "bindip": "0.0.0.0"},
            ],
        )
        assert len(result) == 2
        # First error is for port 80
        assert result[0][0] == "app.schema"
        assert '"0.0.0.0:80"' in result[0][1]
        assert "WebUI Service" in result[0][1]
        assert result[0][2] == errno.EINVAL
        # Second error is for port 22
        assert result[1][0] == "app.schema"
        assert '"0.0.0.0:22"' in result[1][1]
        assert "SSH Service" in result[1][1]
        assert result[1][2] == errno.EINVAL


@pytest.mark.asyncio
async def test_batch_validate_ports_serialized_is_json_safe():
    """Serialized result must contain only JSON-serializable types."""
    import json
    with get_port_service() as port_service:
        result = await port_service.validate_ports(
            "test",
            [
                {"port": 80, "bindip": "0.0.0.0"},
                {"port": 22, "bindip": "0.0.0.0"},
            ],
        )
        # Should not raise - proves the result is JSON serializable
        serialized = json.dumps(result)
        deserialized = json.loads(serialized)
        # json.loads returns lists instead of tuples, so compare as lists
        assert deserialized == [list(entry) for entry in result]


@pytest.mark.asyncio
async def test_batch_validate_ports_serialized_matches_old_endpoint():
    """Serialized output from validate_ports should match what validate_port produces."""
    with get_port_service() as port_service:
        # Get error from old endpoint
        old_verrors = await port_service.validate_port("test", 80, "0.0.0.0")
        old_serialized = list(old_verrors)

        # Get error from new endpoint
        new_serialized = await port_service.validate_ports("test", [{"port": 80, "bindip": "0.0.0.0"}])

        assert old_serialized == new_serialized
