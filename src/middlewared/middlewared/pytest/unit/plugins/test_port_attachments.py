import pytest

from unittest.mock import patch

from middlewared.plugins.ports.ports import PortService
from middlewared.pytest.unit.middleware import Middleware


PORTS_IN_USED = [
    {
        'namespace': 'ssh',
        'title': 'SSH Service',
        'ports': [[
            '0.0.0.0',
            22100
        ]],
        'port_details': [{
            'description': None,
            'ports': [[
                '0.0.0.0',
                22100
            ]]
        }]
    },
    {
        'namespace': 'tftp',
        'title': 'TFTP Service',
        'ports': [[
            '192.168.0.23',
            6900
        ]],
        'port_details': [{
            'description': None,
            'ports': [[
                '192.168.0.23',
                6900
            ]]
        }]
    },
]


@pytest.mark.parametrize('port,bindip', [
    (6900, '192.168.0.23'),
    (6900, '0.0.0.0'),
    (22100, '192.168.0.23'),
    (22100, '0.0.0.0'),
    (22100, '192.168.0.24')
])
@pytest.mark.asyncio
async def test_port_delegate_validation_with_invalid_port_binding(port, bindip):
    m = Middleware()
    with patch('middlewared.plugins.ports.ports.PortService.get_in_use') as get_in_use_port:
        get_in_use_port.return_value = PORTS_IN_USED
        verrors = await PortService(m).validate_port('test', port, bindip)
        assert [e.errmsg for e in verrors.errors] != []


@pytest.mark.parametrize('port,bindip,whitelist_namespace', [
    (6900, '192.168.0.24', None),
    (6000, '0.0.0.0', None),
    (6400, '192.168.0.23', None),
    (22100, '192.168.0.23', 'ssh'),
    (6900, '0.0.0.0', 'tftp'),

])
@pytest.mark.asyncio
async def test_port_delegate_validation_with_valid_port_binding(port, bindip, whitelist_namespace):
    m = Middleware()
    with patch('middlewared.plugins.ports.ports.PortService.get_in_use') as get_in_use_port:
        get_in_use_port.return_value = PORTS_IN_USED
        verrors = await PortService(m).validate_port('test', port, bindip, whitelist_namespace)
        assert [e.errmsg for e in verrors.errors] == []
