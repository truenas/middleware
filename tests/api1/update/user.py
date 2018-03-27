#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS


import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET_USER


# Get the ID of testuser
def test_00_cleanup_tests():
    global userid
    userid = GET_USER("testuser")


# Update the testuser
def test_01_Updating_user_testuser():
    payload = {"bsdusr_username": "testuser",
               "bsdusr_full_name": "Test Renamed",
               "bsdusr_password": "testing123",
               "bsdusr_uid": 1112,
               "bsdusr_home": "/mnt/tank/testuser",
               "bsdusr_mode": "755",
               "bsdusr_shell": "/bin/csh"}
    assert PUT("/account/users/%s/" % userid, payload) == 200


# Update password for testuser
def test_02_Updating_password_for_testuser():
    payload = {"bsdusr_password": "newpasswd"}
    path = "/account/users/%s/password/" % userid
    assert POST(path, payload) == 200
