#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import interface, ip
from functions import GET, PUT, POST, DELETE

aliases = {'address': ip}


def test_01_get_interfaces_name():
    results = GET(f'/interfaces?name={interface}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    assert results.json()[0]["name"] == interface, results.text


def test_02_get_interfaces_aliases_ip():
    results = GET(f'/interfaces?name={interface}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    for aliases_list in results.json()[0]['state']['aliases']:
        assert isinstance(aliases_list['address'], str) is True, results.text
        # no break to look all address value are string
        if ip in aliases_list['address']:
            interface_ip = aliases_list['address']
    assert interface_ip == ip, results.text


def test_03_get_interfaces_aliases_broadcast_ip():
    results = GET(f'/interfaces?name={interface}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    for aliases_list in results.json()[0]['state']['aliases']:
        if ip in aliases_list['address']:
            broadcast_ip = aliases_list['broadcast']
            break
    assert isinstance(broadcast_ip['type'], str) is True, results.text
    aliases['broadcast'] = broadcast_ip

def test_04_get_interfaces_aliases_type():
    results = GET(f'/interfaces?name={interface}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    for aliases_list in results.json()[0]['state']['aliases']:
        assert isinstance(aliases_list['type'], str) is True, results.text
        # no break to look all address value are string
        if ip in aliases_list['address']:
            types = aliases_list['type']
    assert types in ('INET', 'INET6'), results.text
    aliases['type'] = types


def test_05_get_interfaces_aliases_netmask():
    results = GET(f'/interfaces?name={interface}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    for aliases_list in results.json()[0]['state']['aliases']:
        if ip in aliases_list['address']:
            netmask = aliases_list['netmask']
            break
    assert isinstance(netmask, int) is True, results.text
    aliases['netmask'] = netmask


def test_06_get_interfaces_ipv4_in_use():
    global results
    results = POST("/interfaces/ip_in_use/", {"ipv4": True})
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('dkey', ['type', 'address', 'netmask', 'broadcast'])
def test_07_look_at_interfaces_ipv4_in_use_output_(dkey):
    assert results.json()[0][dkey] == aliases[dkey], results.text


def test_08_set_main_interfaces_ipv4_to_false():
    payload = {
        'ipv4_dhcp': False,
        "aliases": [f"{ip}/{aliases['netmask']}"]
    }
    results = PUT(f'/interfaces/id/{interface}/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    assert results.json()['ipv4_dhcp'] is False, results.text


def test_09_looking_main_interfaces_ipv4_dhcp_if_is_false():
    results = GET(f'/interfaces/id/{interface}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    assert results.json()['ipv4_dhcp'] is False, results.text


@pytest.mark.parametrize('dkey', ['type', 'address', 'netmask'])
def test_10_look_at_interfaces_aliases_output_(dkey):
    results = GET(f'/interfaces/id/{interface}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    assert results.json()['aliases'][0][dkey] == aliases[dkey], results.text


def test_11_creating_vlan1_interface():
    global payload
    payload = {
        "ipv4_dhcp": True,
        "vlan_parent_interface": interface,
        "name": "vlan1",
        "type": "VLAN",
        "vlan_tag": 1,
        "vlan_pcp": 1
    }
    global results
    results = POST('/interfaces/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    global interfaces_id
    interfaces_id = results.json()['id']


@pytest.mark.parametrize('dkey', ["ipv4_dhcp", "name", "vlan_parent_interface",
                                  "type", "vlan_tag", "vlan_pcp"])
def test_12_compare_payload_with_created_vlan1_interfaces_result_output_(dkey):
    assert results.json()[dkey] == payload[dkey], results.text


def test_13_get_the_vlan1_interface_results():
    global results
    results = GET(f'/interfaces/id/{interfaces_id}/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text


@pytest.mark.parametrize('dkey', ["ipv4_dhcp", "name", "vlan_parent_interface",
                                  "type", "vlan_tag", "vlan_pcp"])
def test_14_compare_payload_with_get_vlan1_interface_result_output_(dkey):
    assert results.json()[dkey] == payload[dkey], results.text


def test_15_get_interfaces_has_pending_changes():
    results = GET('/interfaces/has_pending_changes')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool) is True, results.text
    assert results.json() is True, results.text


def test_16_commite_interface():
    payload = {
        "rollback": True,
        "checkin_timeout": 10
    }
    results = POST('/interfaces/commit/', payload)
    assert results.status_code == 200, results.text


def test_17_get_interfaces_checkin_waiting():
    results = GET('/interfaces/checkin_waiting/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool) is True, results.text
    assert results.json() is True, results.text


def test_18_get_interfaces_checkin():
    results = GET('/interfaces/checkin/')
    assert results.status_code == 200, results.text
    assert results.json() is None, results.text


def test_19_get_interfaces_has_pending_changes():
    results = GET('/interfaces/has_pending_changes')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool) is True, results.text
    assert results.json() is False, results.text


def test_20_delete_interfaces_vlan1():
    results = DELETE(f'/interfaces/id/{interfaces_id}')
    assert results.status_code == 200, results.text
