from copy import deepcopy
from middlewared.plugins.network_.utils import find_interface_changes, retrieve_added_interfaces, retrieve_removed_interfaces


ORIGINAL = {
    'interfaces': [
        {
            'id': 1,
            'int_interface': 'enp1s0',
            'int_name': '',
            'int_dhcp': False,
            'int_address': '192.0.1.253',
            'int_address_b': '',
            'int_version': 4,
            'int_netmask': 24,
            'int_ipv6auto': False,
            'int_vip': '',
            'int_vhid': None,
            'int_critical': False,
            'int_group': None,
            'int_mtu': 1500
        },
        {
            'id': 2,
            'int_interface': 'enp10s0',
            'int_name': '',
            'int_dhcp': True,
            'int_address': '',
            'int_address_b': '',
            'int_version': '',
            'int_netmask': '',
            'int_ipv6auto': False,
            'int_vip': '',
            'int_vhid': None,
            'int_critical': False,
            'int_group': None,
            'int_mtu': 1500
        },
        {
            'id': 28,
            'int_interface': 'br0',
            'int_name': '',
            'int_dhcp': False,
            'int_address': '',
            'int_address_b': '',
            'int_version': '',
            'int_netmask': '',
            'int_ipv6auto': False,
            'int_vip': '',
            'int_vhid': None,
            'int_critical': False,
            'int_group': None,
            'int_mtu': 1500
        },
        {
            'id': 29,
            'int_interface': 'bond0',
            'int_name': '',
            'int_dhcp': False,
            'int_address': '',
            'int_address_b': '',
            'int_version': '',
            'int_netmask': '',
            'int_ipv6auto': False,
            'int_vip': '',
            'int_vhid': None,
            'int_critical': False,
            'int_group': None,
            'int_mtu': 1500
        },
        {
            'id': 30,
            'int_interface': 'vlan0',
            'int_name': '',
            'int_dhcp': False,
            'int_address': '',
            'int_address_b': '',
            'int_version': '',
            'int_netmask': '',
            'int_ipv6auto': False,
            'int_vip': '',
            'int_vhid': None,
            'int_critical': False,
            'int_group': None,
            'int_mtu': 1500
        }
    ],
    'alias': [],
    'bridge': [
        {
            'id': 20,
            'members': ['enp17s0'],
            'stp': True,
            'enable_learning': True,
            'interface': 28
        }
    ],
    'vlan': [
        {
            'id': 5,
            'vlan_vint': 'vlan0',
            'vlan_pint': 'enp1s0',
            'vlan_tag': 23,
            'vlan_description': '',
            'vlan_pcp': None
         }
    ],
    'lagg': [
        {
            'id': 2,
            'lagg_protocol': 'lacp',
            'lagg_xmit_hash_policy': 'layer2+3',
            'lagg_lacpdu_rate': 'slow',
            'lagg_interface': 29
        }
    ],
    'laggmembers': [
        {
            'id': 22,
            'lagg_ordernum': 0,
            'lagg_physnic': 'enp16s0',
            'lagg_interfacegroup': 2,
            'lagg_interface': 'bond0'
        }
    ],
    'ipv4gateway': {
        'gc_ipv4gateway': '192.168.122.1'
    }
}


def test_physical_interface_changes():
    current = deepcopy(ORIGINAL)
    current['interfaces'][0]['int_dhcp'] = True
    current['interfaces'][1]['int_netmask'] = '24'
    assert set(find_interface_changes(ORIGINAL, current)) == {'enp1s0', 'enp10s0'}


def test_bridge_interface_changes():
    current = deepcopy(ORIGINAL)
    current['interfaces'][2]['int_dhcp'] = True
    assert set(find_interface_changes(ORIGINAL, current)) == {'br0'}


def test_bridge_members_changes():
    current = deepcopy(ORIGINAL)
    current['bridge'][0]['stp'] = False
    assert set(find_interface_changes(ORIGINAL, current)) == {'br0'}


def test_bond_interface_changes():
    current = deepcopy(ORIGINAL)
    current['interfaces'][3]['int_dhcp'] = True
    assert set(find_interface_changes(ORIGINAL, current)) == {'bond0'}


def test_lagg_changes():
    current = deepcopy(ORIGINAL)
    current['lagg'][0]['lagg_lacpdu_rate'] = False
    assert set(find_interface_changes(ORIGINAL, current)) == {'bond0'}


def test_lagg_members_changes():
    current = deepcopy(ORIGINAL)
    current['laggmembers'][0]['vlan_tag'] = 231
    assert set(find_interface_changes(ORIGINAL, current)) == {'bond0'}


def test_vlan_interface_changes():
    current = deepcopy(ORIGINAL)
    current['interfaces'][4]['int_dhcp'] = True
    assert set(find_interface_changes(ORIGINAL, current)) == {'vlan0'}


def test_vlan_changes():
    current = deepcopy(ORIGINAL)
    current['vlan'][0]['int_dhcp'] = True
    assert set(find_interface_changes(ORIGINAL, current)) == {'vlan0'}


def test_check_interface_removed():
    current = deepcopy(ORIGINAL)
    current['interfaces'].pop(0)
    assert set(retrieve_removed_interfaces(ORIGINAL, current)) == {'enp1s0'}


def test_check_interface_added():
    current = deepcopy(ORIGINAL)
    new_interface = deepcopy(current['interfaces'][0])
    new_interface['int_interface'] = 'enp11s0'
    current['interfaces'].append(new_interface)
    assert set(retrieve_added_interfaces(ORIGINAL, current)) == {'enp11s0'}
