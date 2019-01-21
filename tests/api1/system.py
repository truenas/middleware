#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, SSH_TEST, vm_state, vm_start, ping_host
from functions import DELETE
from auto_config import user, password, ip, vm_name, interface

tun_list = [
    "tun_var",
    "tun_comment",
    "tun_enabled",
    "tun_value",
    "tun_type",
]


def test_01_checking_system_version():
    results = GET("/system/version/")
    assert results.status_code == 200, results.text


# Set the timezone
def test_02_Setting_timezone():
    payload = {"stg_timezone": "America/New_York"}
    results = PUT("/system/settings/", payload)
    assert results.status_code == 200, results.text


def test_03_verify_timezon_has_change():
    results = GET("/system/settings/")
    assert results.status_code == 200, results.text
    assert results.json()['stg_timezone'] == "America/New_York", results.text


# Create loader tunable
def test_04_create_system_tunable_dummynet():
    global payload, results, tunable_id
    payload = {
        "tun_var": "dummynet_load",
        "tun_comment": "tunable dummynet test",
        "tun_enabled": True,
        "tun_value": "YES",
        "tun_type": "loader"
    }
    results = POST("/system/tunable/", payload)
    assert results.status_code == 201, results.text
    tunable_id = results.json()['id']


@pytest.mark.parametrize('data', tun_list)
def test_05_verify_created_tunable_dummynet_result_of_(data):
    assert payload[data] == results.json()[data], results.text


# Get loader tunable
def test_06_get_system_tunable_dummynet():
    global results
    results = GET(f"/system/tunable/{tunable_id}")
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', tun_list)
def test_07_verify_get_system_tunable_result_of_(data):
    assert payload[data] == results.json()[data], results.text


# Reboot system to enable tunable
def test_08_reboot_system_to_enable_tunable():
    results = POST("/system/reboot/")
    assert results.status_code == 202, results.text


def test_09_wait_for_reboot():
    if vm_name is not None:
        while vm_state(vm_name) != 'stopped':
            sleep(5)
        assert vm_start(vm_name) is True
    sleep(1)
    while ping_host(ip) is not True:
        sleep(5)
    assert ping_host(ip) is True
    sleep(10)


# Verify loader tunable
def test_10_verify_system_tunable_dummynet_load():
    results = SSH_TEST('kldstat -m dummynet', user, password, ip)
    assert results['result'] is True, results['output']


def test_11_delete_tunable():
    results = DELETE(f"/system/tunable/{tunable_id}/")
    assert results.status_code == 204, results.text


def test_12_tunable_id_has_been_deleted():
    results = GET(f"/system/tunable/{tunable_id}/")
    assert results.status_code == 404, results.text


def test_13_shutdow_system():
    results = POST("/system/shutdown/")
    assert results.status_code == 202, results.text


def test_14_wait_for_system_to_shutdown_with_bhyve():
    if vm_name is not None and interface == 'vtnet0':
        while vm_state(vm_name) != 'stopped':
            sleep(5)
        vm_state(vm_name) == 'stopped'
    else:
        pytest.skip('skip no vm_name')


def test_15_start_vm_bhyve_and_wait_for_freenas_to_be_online():
    if vm_name is not None and interface == 'vtnet0':
        assert vm_start(vm_name) is True
        sleep(1)
        while ping_host(ip) is not True:
            sleep(5)
        assert ping_host(ip) is True
        sleep(10)
    else:
        pytest.skip('skip no vm_name')


def test_16_verify_system_tunable_dummynet_not_loaded():
    results = SSH_TEST('kldstat -m dummynet', user, password, ip)
    assert results['result'] is False, results['output']
