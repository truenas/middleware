#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET_OUTPUT, is_agent_setup, if_key_listed
from auto_config import sshKey


def test_1_Configuring_ssh_settings():
    payload = {"ssh_rootlogin": 'true'}
    assert PUT("/services/ssh/", payload) == 200


def test_2_Enabling_ssh_service():
    payload = {"srv_enable": 'true'}
    assert PUT("/services/services/ssh/", payload) == 200


def test_3_Checking_ssh_enabled():
    assert GET_OUTPUT("/services/services/ssh/", 'srv_state') == "RUNNING"


def test_4_Ensure_ssh_agent_is_setup():
    assert is_agent_setup() is True


def test_5_Ensure_ssh_key_is_up():
    assert if_key_listed() is True


def test_6_Add_ssh_ky_to_root():
    payload = {"bsdusr_sshpubkey": sshKey}
    assert PUT("/account/users/1/", payload) == 200
