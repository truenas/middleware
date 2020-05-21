#!/usr/bin/env python3

import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, SSH_TEST, ping_host
from auto_config import user, ip


def test_01_get_ssh_keyscan_before_reboot():
    global output_before
    cmd = 'ssh-keyscan 127.0.0.1'
    results = SSH_TEST(cmd, user, None, ip)
    assert results['result'] is True, str(results['output'])
    output_before = results['output']


def test_02_reboot_and_wait_for_ping():
    payload = {
        "delay": 0
    }
    results = POST("/system/reboot/", payload)
    assert results.status_code == 200, results.text
    sleep(10)
    while ping_host(ip, 1) is not True:
        sleep(5)
    sleep(10)


def test_03_get_ssh_keyscan_after_reboot():
    global output_after
    cmd = 'ssh-keyscan 127.0.0.1'
    results = SSH_TEST(cmd, user, None, ip)
    assert results['result'] is True, str(results['output'])
    output_after = results['output']


def test_04_compare_ssh_keyscan_output():
    assert output_before == output_after
