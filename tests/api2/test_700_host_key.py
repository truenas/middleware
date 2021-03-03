#!/usr/bin/env python3

import pytest
import sys
import os
import requests
from pytest_dependency import depends
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, SSH_TEST, ping_host
from auto_config import user, ip, ha, scale, dev_test

if dev_test:
    reason = 'Skip for testing'
else:
    reason = 'Skipping test for HA' if ha else 'Skipping test for SCALE'
pytestmark = pytest.mark.skipif(ha or scale or dev_test, reason=reason)


def test_01_verify_ssh_settings_for_root_login_before_reboot():
    results = GET("/ssh/")
    assert results.status_code == 200, results.text
    assert results.json()["rootlogin"] is True, results.text


def test_02_verify_ssh_enable_at_boot_before_reboot():
    results = GET("/service?service=ssh")
    assert results.json()[0]['enable'] is True


def test_03_verify_if_ssh_is_running_before_reboot():
    results = GET("/service?service=ssh")
    assert results.json()[0]['state'] == "RUNNING"


def test_04_get_ssh_keyscan_before_reboot(request):
    depends(request, ["ssh_key"], scope="session")
    global output_before
    cmd = 'ssh-keyscan 127.0.0.1'
    results = SSH_TEST(cmd, user, None, ip)
    assert results['result'] is True, str(results['output'])
    output_before = results['output']


def test_05_reboot_system():
    payload = {
        "delay": 0
    }
    results = POST("/system/reboot/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.timeout(600)
def test_06_wait_for_middleware_to_be_online():
    while ping_host(ip, 1) is True:
        sleep(5)
    while ping_host(ip, 1) is not True:
        sleep(5)
    sleep(10)
    status_code = 0
    while status_code != 200:
        try:
            status_code = GET('/system/info/').status_code
        except requests.exceptions.ConnectionError:
            sleep(1)
            continue


def test_07_verify_ssh_settings_for_root_login_after_reboot():
    results = GET("/ssh/")
    assert results.status_code == 200, results.text
    assert results.json()["rootlogin"] is True, results.text


def test_08_verify_ssh_enable_at_boot_after_reboot():
    results = GET("/service?service=ssh")
    assert results.json()[0]['enable'] is True


def test_09_verify_if_ssh_is_running_after_reboot():
    results = GET("/service?service=ssh")
    assert results.json()[0]['state'] == "RUNNING"


def test_10_get_ssh_keyscan_after_reboot(request):
    depends(request, ["ssh_key"], scope="session")
    global output_after
    cmd = 'ssh-keyscan 127.0.0.1'
    results = SSH_TEST(cmd, user, None, ip)
    assert results['result'] is True, str(results['output'])
    output_after = results['output']


def test_11_compare_ssh_keyscan_output():
    for line in output_after:
        assert line in output_before
