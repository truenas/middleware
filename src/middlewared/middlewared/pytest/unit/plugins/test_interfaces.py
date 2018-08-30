import pytest

from asynctest import ANY, Mock

from middlewared.service import ValidationErrors
from middlewared.plugins.network import InterfacesService
from middlewared.pytest.unit.middleware import Middleware


INTERFACES = [
    {
        'id': 'em0',
        'name': 'em0',
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
        'aliases': [],
        'options': '',
        'ipv4_dhcp': False,
        'ipv6_auto': False,
        'state': {
            'cloned': False,
        },
    },
]


@pytest.mark.asyncio
async def test__interfaces_service__create_lagg_invalid_ports():

    m = Middleware()
    m['interfaces.query'] = Mock(return_value=INTERFACES)
    verrors = Mock()

    with pytest.raises(ValidationErrors) as ve:
        await InterfacesService(m).create({
            'type': 'LINK_AGGREGATION',
            'lag_protocol': 'LACP',
            'lag_ports': ['em0', 'igb2'],
        })
    assert 'interface_create.lag_ports.1' in ve.value


@pytest.mark.asyncio
async def test__interfaces_service__create_lagg_invalid_name():

    m = Middleware()
    m['interfaces.query'] = Mock(return_value=INTERFACES)
    verrors = Mock()

    with pytest.raises(ValidationErrors) as ve:
        await InterfacesService(m).create({
            'type': 'LINK_AGGREGATION',
            'name': 'mylag11',
            'lag_protocol': 'LACP',
            'lag_ports': ['em0'],
        })
    assert 'interface_create.name' in ve.value


@pytest.mark.asyncio
async def test__interfaces_service__create_lagg():

    m = Middleware()
    m['interfaces.query'] = Mock(return_value=INTERFACES)
    m['datastore.query'] = Mock(return_value=[])
    m['datastore.insert'] = Mock(return_value=5)
    verrors = Mock()

    await InterfacesService(m).create({
        'type': 'LINK_AGGREGATION',
        'lag_protocol': 'LACP',
        'lag_ports': ['em0', 'em1'],
    })


@pytest.mark.asyncio
async def test__interfaces_service__create_vlan_invalid_parent():

    m = Middleware()
    m['interfaces.query'] = Mock(return_value=INTERFACES)
    verrors = Mock()

    with pytest.raises(ValidationErrors) as ve:
        await InterfacesService(m).create({
            'type': 'VLAN',
            'name': 'myvlan1',
            'vlan_tag': 5,
            'vlan_parent_interface': 'igb2',
        })
    assert 'interface_create.vlan_parent_interface' in ve.value


@pytest.mark.asyncio
async def test__interfaces_service__create_vlan_invalid_name():

    m = Middleware()
    m['interfaces.query'] = Mock(return_value=INTERFACES)
    verrors = Mock()

    with pytest.raises(ValidationErrors) as ve:
        await InterfacesService(m).create({
            'type': 'VLAN',
            'name': 'myvlan1',
            'vlan_tag': 5,
            'vlan_parent_interface': 'em0',
        })
    assert 'interface_create.name' in ve.value


@pytest.mark.asyncio
async def test__interfaces_service__create_vlan():

    m = Middleware()
    m['interfaces.query'] = Mock(return_value=INTERFACES)
    m['datastore.query'] = Mock(return_value=[])
    m['datastore.insert'] = Mock(return_value=5)
    verrors = Mock()

    await InterfacesService(m).create({
        'type': 'VLAN',
        'vlan_tag': 5,
        'vlan_parent_interface': 'em0',
    })
