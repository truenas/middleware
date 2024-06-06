import copy
import pytest
from middlewared.plugins.network_.utils import find_interface_changes, retrieve_added_removed_interfaces

ORIGINAL = {
    'interfaces': [
        {
            'id': 1,
            'int_interface': 'enp1s0',
            'int_name': '',
            'int_dhcp': False,
            'int_address': '192.168.122.253',
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
            'id': 32,
            'int_interface': 'br0',
            'int_name': '',
            'int_dhcp': False,
            'int_address': '10.2.31.23',
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
            'id': 33,
            'int_interface': 'br1',
            'int_name': '',
            'int_dhcp': False,
            'int_address': '34.32.123.22',
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
            'id': 34,
            'int_interface': 'bond0',
            'int_name': 'bond interface',
            'int_dhcp': False,
            'int_address': '172.3.2.1',
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
            'id': 35,
            'int_interface': 'bond1',
            'int_name': '',
            'int_dhcp': False,
            'int_address': '56.43.1.23',
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
            'id': 36,
            'int_interface': 'vlan0',
            'int_name': '',
            'int_dhcp': False,
            'int_address': '174.21.3.2',
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
            'id': 37,
            'int_interface': 'vlan1',
            'int_name': '',
            'int_dhcp': False,
            'int_address': '87.21.3.2',
            'int_address_b': '',
            'int_version': 4,
            'int_netmask': 24,
            'int_ipv6auto': False,
            'int_vip': '',
            'int_vhid': None,
            'int_critical': False,
            'int_group': None,
            'int_mtu': 1500
        }
    ],
    'alias': [
        {
            'id': 3,
            'alias_address': '10.2.3.12',
            'alias_version': 4,
            'alias_netmask': 24,
            'alias_address_b': '',
            'alias_vip': '',
            'alias_interface': 32
        },
        {
            'id': 4,
            'alias_address': '10.32.32.14',
            'alias_version': 4,
            'alias_netmask': 24,
            'alias_address_b': '',
            'alias_vip': '',
            'alias_interface': 32
        },
        {
            'id': 5,
            'alias_address': '32.32.12.43',
            'alias_version': 4,
            'alias_netmask': 24,
            'alias_address_b': '',
            'alias_vip': '',
            'alias_interface': 33
        },
        {
            'id': 6,
            'alias_address': '172.3.2.3',
            'alias_version': 4,
            'alias_netmask': 24,
            'alias_address_b': '',
            'alias_vip': '',
            'alias_interface': 34
        },
        {
            'id': 8,
            'alias_address': '56.54.32.3',
            'alias_version': 4,
            'alias_netmask': 24,
            'alias_address_b': '',
            'alias_vip': '',
            'alias_interface': 35
        },
        {
            'id': 9,
            'alias_address': '56.53.32.5',
            'alias_version': 4,
            'alias_netmask': 24,
            'alias_address_b': '',
            'alias_vip': '',
            'alias_interface': 35
        },
        {
            'id': 10,
            'alias_address': '173.21.23.4',
            'alias_version': 4,
            'alias_netmask': 24,
            'alias_address_b': '',
            'alias_vip': '',
            'alias_interface': 36
        },
        {
            'id': 11,
            'alias_address': '34.21.23.4',
            'alias_version': 4,
            'alias_netmask': 24,
            'alias_address_b': '',
            'alias_vip': '',
            'alias_interface': 37
        },
        {
            'id': 12,
            'alias_address': '176.2.1.2',
            'alias_version': 4,
            'alias_netmask': 24,
            'alias_address_b': '',
            'alias_vip': '',
            'alias_interface': 34
        }
    ],
    'bridge': [
        {
            'id': 21,
            'members': ['enp10s0'],
            'stp': True,
            'enable_learning': True,
            'interface': 32
        },
        {
            'id': 22,
            'members': ['enp16s0', 'enp17s0'],
            'stp': True,
            'enable_learning': True,
            'interface': 33
         }
    ],
    'vlan': [
        {
            'id': 6,
            'vlan_vint': 'vlan0',
            'vlan_pint': 'enp22s0',
            'vlan_tag': 231,
            'vlan_description': '',
            'vlan_pcp': 1
        },
        {
            'id': 7,
            'vlan_vint': 'vlan1',
            'vlan_pint': 'enp23s0',
            'vlan_tag': 231,
            'vlan_description': '',
            'vlan_pcp': 0
        }
    ],
    'lagg': [
        {
            'id': 4,
            'lagg_protocol': 'lacp',
            'lagg_xmit_hash_policy': 'LAYER2+3',
            'lagg_lacpdu_rate': 'SLOW',
            'lagg_interface': 34
        },
        {
            'id': 5,
            'lagg_protocol': 'loadbalance',
            'lagg_xmit_hash_policy': 'layer2+3',
            'lagg_lacpdu_rate': None,
            'lagg_interface': 35
        }
    ],
    'laggmembers': [
        {
            'id': 29,
            'lagg_ordernum': 0,
            'lagg_physnic': 'enp21s0',
            'lagg_interfacegroup': 5,
            'lagg_interface': 'bond1'
        },
        {
            'id': 32,
            'lagg_ordernum': 0,
            'lagg_physnic': 'enp18s0',
            'lagg_interfacegroup': 4,
            'lagg_interface': 'bond0'
        },
        {
            'id': 33,
            'lagg_ordernum': 1,
            'lagg_physnic': 'enp20s0',
            'lagg_interfacegroup': 4,
            'lagg_interface': 'bond0'
        }
    ],
}


@pytest.mark.parametrize('member_id,action,payload,changed_iface', [
    (None, 'add', {
        'id': 35,
        'lagg_ordernum': 2,
        'lagg_physnic': 'enp21s0',
        'lagg_interfacegroup': 4,
        'lagg_interface': 'bond0'
    }, 'bond0'),
    (32, 'remove', {}, 'bond0'),
])
def test_bond_changed(member_id, action, payload, changed_iface):
    current = copy.deepcopy(ORIGINAL)
    if action == 'add':
        current['laggmembers'].append(payload)
    else:
        current['laggmembers'].pop(next(i for i, d in enumerate(current['laggmembers']) if d['id'] == member_id))

    assert changed_iface in find_interface_changes(ORIGINAL, current)
    assert changed_iface not in retrieve_added_removed_interfaces(ORIGINAL, current, 'added')
    assert changed_iface not in retrieve_added_removed_interfaces(ORIGINAL, current, 'removed')


def test_vlan_changed():
    current = copy.deepcopy(ORIGINAL)
    current['vlan'][0]['vlan_description'] = 'Changed description'
    assert 'vlan0' in find_interface_changes(ORIGINAL, current)
    assert 'vlan0' not in retrieve_added_removed_interfaces(ORIGINAL, current, 'added')
    assert 'vlan0' not in retrieve_added_removed_interfaces(ORIGINAL, current, 'removed')


def test_alias_changed():
    current = copy.deepcopy(ORIGINAL)
    current['alias'][0]['alias_netmask'] = 25
    assert 'br0' in find_interface_changes(ORIGINAL, current)
    assert 'br0' not in retrieve_added_removed_interfaces(ORIGINAL, current, 'added')
    assert 'br0' not in retrieve_added_removed_interfaces(ORIGINAL, current, 'removed')


def test_bridge_changed():
    current = copy.deepcopy(ORIGINAL)
    current['bridge'][1]['stp'] = False
    assert 'br1' in find_interface_changes(ORIGINAL, current)
    assert 'br1' not in retrieve_added_removed_interfaces(ORIGINAL, current, 'added')
    assert 'br1' not in retrieve_added_removed_interfaces(ORIGINAL, current, 'removed')


def test_interface_changed():
    current = copy.deepcopy(ORIGINAL)
    changed_ifaces = []
    iface_id_mapping = {i['id']: i['int_interface'] for i in ORIGINAL['interfaces']}
    for index, interface in enumerate(current['interfaces']):
        if index % 2 == 0:
            interface['int_mtu'] = 1600
            changed_ifaces.append(iface_id_mapping[interface['id']])

    assert set(changed_ifaces) == set(find_interface_changes(ORIGINAL, current))


def test_addition_of_interfaces():
    current = copy.deepcopy(ORIGINAL)
    current['interfaces'].append({
        'id': 200,
        'int_interface': 'enps10s0',
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
    })

    assert 'enps10s0' not in find_interface_changes(ORIGINAL, current)
    assert 'enps10s0' in retrieve_added_removed_interfaces(ORIGINAL, current, 'added')
    assert 'enps10s0' not in retrieve_added_removed_interfaces(ORIGINAL, current, 'removed')


def test_removal_of_interfaces():
    current = copy.deepcopy(ORIGINAL)
    current['interfaces'].pop(0)
    assert 'enp1s0' not in find_interface_changes(ORIGINAL, current)
    assert 'enp1s0' not in retrieve_added_removed_interfaces(ORIGINAL, current, 'added')
    assert 'enp1s0' in retrieve_added_removed_interfaces(ORIGINAL, current, 'removed')
