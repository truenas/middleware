#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
from time import sleep
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, is_agent_setup, if_key_listed, SSH_TEST
from auto_config import sshKey, user, password, ha

if "controller1_ip" in os.environ:
    ip = os.environ["controller1_ip"]
else:
    from auto_config import ip


def test_01_Configuring_ssh_settings_for_root_login():
    payload = {"rootlogin": True}
    results = PUT("/ssh/", payload, controller_a=ha)
    assert results.status_code == 200, results.text


def test_02_Enabling_ssh_service_at_boot():
    payload = {'enable': True}
    results = PUT("/service/id/ssh/", payload, controller_a=ha)
    assert results.status_code == 200, results.text


def test_03_Checking_ssh_enable_at_boot():
    results = GET("/service?service=ssh", controller_a=ha)
    assert results.json()[0]['enable'] is True


def test_04_Start_ssh_service():
    payload = {"service": "ssh"}
    results = POST("/service/start/", payload, controller_a=ha)
    assert results.status_code == 200, results.text
    sleep(1)


def test_05_Checking_if_ssh_is_running():
    results = GET("/service?service=ssh", controller_a=ha)
    assert results.json()[0]['state'] == "RUNNING"


@pytest.mark.dependency(name="ssh_password")
def test_06_test_ssh():
    cmd = 'ls -la'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_07_Ensure_ssh_agent_is_setup():
    assert is_agent_setup() is True


def test_08_Ensure_ssh_key_is_up():
    assert if_key_listed() is True


def test_09_Add_ssh_ky_to_root():
    payload = {"sshpubkey": sshKey}
    results = PUT("/user/id/1/", payload, controller_a=ha)
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="ssh_key")
def test_10_test_ssh_key(request):
    depends(request, ["ssh_password"])
    cmd = 'ls -la'
    results = SSH_TEST(cmd, user, None, ip)
    assert results['result'] is True, results['output']
