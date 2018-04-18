#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, is_agent_setup, if_key_listed, SSH_TEST
from auto_config import sshKey, password, user, ip


def test_01_Configuring_ssh_settings_for_root_login():
    payload = {"rootlogin": True}
    results = PUT("/ssh", payload)
    assert results.status_code == 200, results.text


def test_02_Enabling_ssh_service_at_boot():
    payload = {'enable': True}
    results = PUT("/service/id/11", payload)
    assert results.status_code == 200, results.text


def test_03_Checking_ssh_enable_at_boot():
    results = GET("/service")
    assert results.json()[7]['enable'] == True


def test_04_Start_ssh_service():
    payload = {"service": "ssh", "service-control": {"onetime": True}}
    results = POST("/service/start", payload)
    assert results.status_code == 200, results.text


def test_05_Checking_if_ssh_is_running():
    results = GET("/service")
    assert results.json()[7]['state'] == "RUNNING"


def test_06_Ensure_ssh_agent_is_setup():
    assert is_agent_setup() is True


def test_07_Ensure_ssh_key_is_up():
    assert if_key_listed() is True


def test_08_Add_ssh_ky_to_root():
    payload = {"sshpubkey": sshKey}
    results = PUT("/user/id/1", payload)
    assert results.status_code == 200, results.text


def test_09_test_ssh_key():
    cmd = 'ls -la'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
