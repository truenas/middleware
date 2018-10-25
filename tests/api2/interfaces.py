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

broadcast = ip.replace(ip.split('.')[3], '255')
aliases = {'address': ip, 'broadcast': broadcast}


def test_01_get_interfaces_name():
    results = GET(f'/interfaces?name={interface}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    assert results.json()[0]["name"] == interface, results.text


def test_02_get_interfaces_aliases_ip():
    results = GET(f'/interfaces?name={interface}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    interface_ip = results.json()[0]['state']['aliases'][1]['address']
    assert interface_ip == ip, results.text


def test_03_get_interfaces_aliases_broadcast_ip():
    results = GET(f'/interfaces?name={interface}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    broadcast_ip = results.json()[0]['state']['aliases'][1]['broadcast']
    assert broadcast_ip == broadcast, results.text


def test_04_get_interfaces_aliases_type():
    results = GET(f'/interfaces?name={interface}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    broadcast_ip = results.json()[0]['state']['aliases'][1]['type']
    aliases['type'] = broadcast_ip
    assert isinstance(broadcast_ip, str) is True, results.text


def test_05_get_interfaces_aliases_netmask():
    results = GET(f'/interfaces?name={interface}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    netmask = results.json()[0]['state']['aliases'][1]['netmask']
    aliases['netmask'] = netmask
    assert isinstance(netmask, int) is True, results.text


def test_06_set_main_interfaces_ipv4_to_false():
    payload = {'ipv4_dhcp': False}
    results = PUT(f'/interfaces/id/{interface}/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    assert results.json()['ipv4_dhcp'] is False, results.text


def test_07_looking_main_interfaces_ipv4_dhcp_if_is_false():
    results = GET(f'/interfaces/id/{interface}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    assert results.json()['ipv4_dhcp'] is False, results.text


def test_08_creating_vlan1_interface():
    global payload
    payload = {
        "ipv4_dhcp": True,
        "name": "vlan2",
        "vlan_parent_interface": interface,
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
def test_09_looking_at_vlan1_created_interfaces_results_output_(dkey):
    assert results.json()[dkey] == payload[dkey], results.text


def test_10_get_the_vlan1_interface_results():
    global results
    results = GET(f'/interfaces/id/{interfaces_id}/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text


@pytest.mark.parametrize('dkey', ["ipv4_dhcp", "name", "vlan_parent_interface",
                                  "type", "vlan_tag", "vlan_pcp"])
def test_11_looking_at_vlan1_interface_results_output_(dkey):
    assert results.json()[dkey] == payload[dkey], results.text


def test_12_get_interfaces_ipv4_in_use():
    global results
    results = POST("/interfaces/ip_in_use/", {"ipv4": True})
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('dkey', ['type', 'address', 'netmask', 'broadcast'])
def test_13_look_at_interfaces_ipv4_in_use_output_(dkey):
    assert results.json()[0][dkey] == aliases[dkey], results.text


def test_14_get_interfaces_checkin_waiting():
    results = GET('/interfaces/checkin_waiting/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool) is True, results.text


def test_15_get_interfaces_checkin():
    results = GET('/interfaces/checkin/')
    assert results.status_code == 200, results.text
    assert results.json() is None, results.text


def test_16_get_interfaces_has_pending_changes():
    results = GET('/interfaces/has_pending_changes')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool) is True, results.text


def test_17_delete_interfaces_vlan1():
    results = DELETE(f'/interfaces/id/{interfaces_id}')
    assert results.status_code == 200, results.text
