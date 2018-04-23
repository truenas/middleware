#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET, is_agent_setup, if_key_listed
from auto_config import sshKey


def test_01_Configuring_ssh_settings():
    payload = {"ssh_rootlogin": 'true'}
    results = PUT("/services/ssh/", payload)
    assert results.status_code == 200, results.text


def test_02_Enabling_ssh_service():
    payload = {"srv_enable": 'true'}
    results = PUT("/services/services/ssh/", payload)
    assert results.status_code == 200, results.text


def test_03_Checking_ssh_enabled():
    results = GET("/services/services/ssh/")
    assert results.json()['srv_state'] == "RUNNING", results.text


def test_04_Ensure_ssh_agent_is_setup():
    assert is_agent_setup() is True


def test_05_Ensure_ssh_key_is_up():
    assert if_key_listed() is True


def test_06_Add_ssh_ky_to_root():
    payload = {"bsdusr_sshpubkey": sshKey}
    results = PUT("/account/users/1/", payload)
    assert results.status_code == 200, results.text
