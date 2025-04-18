import copy
from unittest.mock import Mock

import pytest

from middlewared.service import ValidationErrors
from middlewared.plugins.network import InterfaceService
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import Middleware


INTERFACES = [
    {
        'id': 'em0',
        'name': 'em0',
        'fake': False,
        'type': 'PHYSICAL',
        'aliases': [],
        'options': '',
        'ipv4_dhcp': False,
        'ipv6_auto': False,
        'state': {
            'cloned': False,
        },
    },
    {
        'id': 'em1',
        'name': 'em1',
        'fake': False,
        'type': 'PHYSICAL',
        'aliases': [],
        'options': '',
        'ipv4_dhcp': False,
        'ipv6_auto': False,
        'state': {
            'cloned': False,
        },
    },
]

INTERFACES_WITH_VLAN = INTERFACES + [
    {
        'id': 'vlan5',
        'name': 'vlan5',
        'fake': False,
        'type': 'VLAN',
        'aliases': [],
        'options': '',
        'ipv4_dhcp': False,
        'ipv6_auto': False,
        'state': {
            'cloned': True,
        },
        'vlan_tag': 5,
        'vlan_parent_interface': 'em0',
    },
]


INTERFACES_WITH_LAG = INTERFACES + [
    {
        'id': 'bond0',
        'name': 'bond0',
        'fake': False,
        'type': 'LINK_AGGREGATION',
        'aliases': [],
        'options': '',
        'ipv4_dhcp': False,
        'ipv6_auto': False,
        'state': {
            'cloned': True,
        },
        'lag_ports': ['em0'],
    },
]


INTERFACES_WITH_BRIDGE = INTERFACES + [
    {
        'id': 'br0',
        'name': 'br0',
        'fake': False,
        'type': 'BRIDGE',
        'aliases': [],
        'options': '',
        'ipv4_dhcp': False,
        'ipv6_auto': False,
        'state': {
            'cloned': True,
        },
        'bridge_members': ['em0'],
    },
]


def mock_datastore_query_side_effect():
    return Mock(
        side_effect=lambda method, *args: {
            'network.interfaces': Mock(return_value=[]),
            'network.alias': Mock(return_value=[]),
            'network.bridge': Mock(return_value=[]),
            'network.lagginterface': Mock(return_value=[]),
            'network.vlan': Mock(return_value=[]),
            'network.lagginterfacemembers': Mock(return_value=[]),
            'network.globalconfiguration': Mock(return_value={'gc_ipv4gateway': ''}),
        }[method](*args)
    )


@pytest.mark.asyncio
async def test__interfaces_service__create_bridge_invalid_ports():

    m = Middleware()
    m['interface.query'] = Mock(return_value=INTERFACES)
    m['datastore.query'] = Mock(return_value=[])
    m['network.common.check_failover_disabled'] = Mock()

    with pytest.raises(ValidationErrors) as ve:
        await create_service(m, InterfaceService).do_create({
            'type': 'BRIDGE',
            'bridge_members': ['em0', 'igb2'],
        })
    assert 'interface_create.bridge_members.1' in ve.value


@pytest.mark.asyncio
async def test__interfaces_service__create_bridge_invalid_ports_used():

    m = Middleware()
    m['interface.query'] = Mock(return_value=INTERFACES_WITH_BRIDGE)
    m['datastore.query'] = Mock(return_value=[])
    m['network.common.check_failover_disabled'] = Mock()

    with pytest.raises(ValidationErrors) as ve:
        await create_service(m, InterfaceService).do_create({
            'type': 'BRIDGE',
            'bridge_members': ['em0'],
        })
    assert 'interface_create.bridge_members.0' in ve.value


@pytest.mark.asyncio
async def test__interfaces_service__create_lagg_invalid_ports():

    m = Middleware()
    m['interface.query'] = Mock(return_value=INTERFACES)
    m['interface.lag_supported_protocols'] = Mock(return_value=['LACP'])
    m['datastore.query'] = Mock(return_value=[])
    m['network.common.check_failover_disabled'] = Mock()

    with pytest.raises(ValidationErrors) as ve:
        await create_service(m, InterfaceService).do_create({
            'type': 'LINK_AGGREGATION',
            'lag_protocol': 'LACP',
            'lag_ports': ['em0', 'igb2'],
        })
    assert 'interface_create.lag_ports.1' in ve.value


@pytest.mark.asyncio
async def test__interfaces_service__create_lagg_invalid_ports_cloned():

    m = Middleware()
    m['interface.query'] = Mock(return_value=INTERFACES_WITH_VLAN)
    m['interface.lag_supported_protocols'] = Mock(return_value=['LACP'])
    m['datastore.query'] = mock_datastore_query_side_effect()
    m['network.common.check_failover_disabled'] = Mock()

    with pytest.raises(ValidationErrors) as ve:
        await create_service(m, InterfaceService).do_create({
            'type': 'LINK_AGGREGATION',
            'lag_protocol': 'LACP',
            'lag_ports': ['em1', 'vlan5'],
        })
    assert 'interface_create.lag_ports.1' in ve.value


@pytest.mark.asyncio
async def test__interfaces_service__create_lagg_invalid_ports_used():

    m = Middleware()
    m['interface.query'] = Mock(return_value=INTERFACES_WITH_LAG)
    m['interface.lag_supported_protocols'] = Mock(return_value=['LACP'])
    m['datastore.query'] = Mock(return_value=[])
    m['network.common.check_failover_disabled'] = Mock()

    with pytest.raises(ValidationErrors) as ve:
        await create_service(m, InterfaceService).do_create({
            'type': 'LINK_AGGREGATION',
            'lag_protocol': 'LACP',
            'lag_ports': ['em0'],
        })
    assert 'interface_create.lag_ports.0' in ve.value


@pytest.mark.asyncio
async def test__interfaces_service__create_lagg():

    m = Middleware()
    m['interface.query'] = Mock(return_value=INTERFACES)
    m['interface.lag_supported_protocols'] = Mock(return_value=['LACP'])
    m['interface.validate_name'] = Mock()
    m['datastore.query'] = mock_datastore_query_side_effect()
    m['datastore.insert'] = Mock(return_value=5)
    m['network.common.check_failover_disabled'] = Mock()

    await create_service(m, InterfaceService).do_create({
        'name': 'bond0',
        'type': 'LINK_AGGREGATION',
        'lag_protocol': 'LACP',
        'lag_ports': ['em0', 'em1'],
    })


@pytest.mark.parametrize('attr_val', [
    ('aliases', [{'address': '192.168.8.2', 'netmask': 24}]),
    ('mtu', 1500),
    ('ipv4_dhcp', True),
    ('ipv6_auto', True),
])
@pytest.mark.asyncio
async def test__interfaces_service__lagg_update_members_invalid(attr_val):

    m = Middleware()
    m['interface.query'] = m._query_filter(INTERFACES_WITH_LAG)
    m['datastore.query'] = Mock(return_value=[])
    m['network.common.check_failover_disabled'] = Mock()

    with pytest.raises(ValidationErrors) as ve:
        await create_service(m, InterfaceService).do_update('em0', {
            attr_val[0]: attr_val[1],
        })
    assert f'interface_update.{attr_val[0]}' in ve.value


@pytest.mark.asyncio
async def test__interfaces_service__create_vlan_invalid_parent():

    m = Middleware()
    m['interface.query'] = Mock(return_value=INTERFACES)
    m['interface.validate_name'] = Mock()
    m['datastore.query'] = Mock(return_value=[])
    m['network.common.check_failover_disabled'] = Mock()

    with pytest.raises(ValidationErrors) as ve:
        await create_service(m, InterfaceService).do_create({
            'type': 'VLAN',
            'name': 'myvlan1',
            'vlan_tag': 5,
            'vlan_parent_interface': 'igb2',
        })
    assert 'interface_create.vlan_parent_interface' in ve.value


@pytest.mark.asyncio
async def test__interfaces_service__create_vlan_invalid_parent_used():

    m = Middleware()
    m['interface.query'] = Mock(return_value=INTERFACES_WITH_LAG)
    m['datastore.query'] = Mock(return_value=[])
    m['network.common.check_failover_disabled'] = Mock()

    with pytest.raises(ValidationErrors) as ve:
        await create_service(m, InterfaceService).do_create({
            'type': 'VLAN',
            'vlan_tag': 5,
            'vlan_parent_interface': 'em0',
        })
    assert 'interface_create.vlan_parent_interface' in ve.value


@pytest.mark.asyncio
async def test__interfaces_service__create_vlan():

    m = Middleware()
    m['interface.query'] = Mock(return_value=INTERFACES)
    m['interface.validate_name'] = Mock()
    m['datastore.query'] = mock_datastore_query_side_effect()
    m['datastore.insert'] = Mock(return_value=5)
    m['network.common.check_failover_disabled'] = Mock()

    await create_service(m, InterfaceService).do_create({
        'name': 'vlan0',
        'type': 'VLAN',
        'vlan_tag': 5,
        'vlan_parent_interface': 'em0',
    })


@pytest.mark.asyncio
async def test__interfaces_service__update_vlan_mtu_bigger_parent():

    m = Middleware()
    m['interface.query'] = m._query_filter(INTERFACES_WITH_VLAN)
    m['interface.validate_name'] = Mock()
    m['datastore.query'] = Mock(return_value=[])
    m['network.common.check_failover_disabled'] = Mock()

    with pytest.raises(ValidationErrors) as ve:
        await create_service(m, InterfaceService).do_update(INTERFACES_WITH_VLAN[-1]['id'], {
            'mtu': 9000,
        })
    assert 'interface_update.mtu' in ve.value


@pytest.mark.asyncio
async def test__interfaces_service__update_two_dhcp():

    interfaces_with_one_dhcp = copy.deepcopy(INTERFACES)
    interfaces_with_one_dhcp[0]['ipv4_dhcp'] = True

    m = Middleware()
    m['interface.query'] = Mock(return_value=interfaces_with_one_dhcp)
    m['datastore.query'] = Mock(return_value=[
        {'int_interface': interfaces_with_one_dhcp[0]['name'], 'int_dhcp': True, 'int_ipv6auto': False}
    ])
    m['network.common.check_failover_disabled'] = Mock()

    update_interface = interfaces_with_one_dhcp[1]

    with pytest.raises(ValidationErrors) as ve:
        await create_service(m, InterfaceService).do_update(
            update_interface['id'], {
                'ipv4_dhcp': True,
            },
        )
    assert 'interface_update.ipv4_dhcp' in ve.value, list(ve.value)


@pytest.mark.asyncio
async def test__interfaces_service__update_two_same_network():

    interfaces_one_network = copy.deepcopy(INTERFACES)
    interfaces_one_network[0]['aliases'] = [
        {'type': 'INET', 'address': '192.168.5.2', 'netmask': 24},
    ]

    m = Middleware()
    m['interface.query'] = Mock(return_value=interfaces_one_network)
    m['datastore.query'] = Mock(return_value=[])
    m['datastore.insert'] = Mock(return_value=5)
    m['network.common.check_failover_disabled'] = Mock()

    update_interface = interfaces_one_network[1]

    with pytest.raises(ValidationErrors) as ve:
        await create_service(m, InterfaceService).do_update(
            update_interface['id'], {
                'aliases': [{'address': '192.168.5.3', 'netmask': 24}],
            },
        )
    assert 'interface_update.aliases.0' in ve.value


@pytest.mark.asyncio
async def test__interfaces_service__update_mtu_options():

    m = Middleware()
    m['interface.query'] = Mock(return_value=INTERFACES)
    m['interface.validate_name'] = Mock()
    m['datastore.query'] = Mock(return_value=[])
    m['datastore.insert'] = Mock(return_value=5)
    m['network.common.check_failover_disabled'] = Mock()

    update_interface = INTERFACES[1]

    with pytest.raises(ValidationErrors) as ve:
        await create_service(m, InterfaceService).do_update(
            update_interface['id'], {
                'options': 'mtu 1550',
            },
        )
    assert 'options: Extra inputs are not permitted' in str(ve.value)
