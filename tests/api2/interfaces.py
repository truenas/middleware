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
from config import *

BRIDGENETMASKReason = "BRIDGENETMASK not in ixautomation.conf"


def test_01_get_interfaces_name():
    results = GET(f'/interfaces?name={interface}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    assert results.json()[0]["name"] == interface, results.text


def test_02_get_interfaces_ip():
    results = GET(f'/interfaces?name={interface}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    interface_ip = results.json()[0]['state']['aliases'][1]['address']
    assert interface_ip == ip, results.text


@pytest.mark.skipif("BRIDGENETMASK" not in locals(),
                    reason=BRIDGENETMASKReason)
def test_03_get_interfaces_netmask():
    results = GET(f'/interfaces?name={interface}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    netmask = results.json()[0]['state']['aliases'][1]['netmask']
    assert netmask == int(BRIDGENETMASK), results.text


def test_04_set_main_interfaces_ipv4_to_false():
    payload = {'ipv4_dhcp': False}
    results = PUT(f'/interfaces/id/{interface}', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    assert results.json()['ipv4_dhcp'] is False, results.text


def test_05_looking_main_interfaces_ipv4_dhcp_if_is_false():
    results = GET(f'/interfaces/id/{interface}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text
    assert results.json()['ipv4_dhcp'] is False, results.text


def test_06_creating_vlan1_interface():
    global payload
    payload = {
        "ipv4_dhcp": True,
        "name": "vlan1",
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
def test_07_looking_at_vlan1_created_interfaces_results_output_(dkey):
    assert results.json()[dkey] == payload[dkey], results.text


def test_08_get_the_vlan1_interface_results():
    global results
    results = GET(f'/interfaces/id/{interfaces_id}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict) is True, results.text


@pytest.mark.parametrize('dkey', ["ipv4_dhcp", "name", "vlan_parent_interface",
                                  "type", "vlan_tag", "vlan_pcp"])
def test_09_looking_at_vlan1_interface_results_output_(dkey):
    assert results.json()[dkey] == payload[dkey], results.text


def test_10_delete_interfaces_vlan1():
    results = DELETE(f'/interfaces/id/{interfaces_id}')
    assert results.status_code == 200, results.text
