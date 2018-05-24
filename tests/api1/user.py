#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET_USER, DELETE, PUT


# Create tests
def test_01_Creating_home_dataset_tank_sur_testuser():
    payload = {"name": "testuser"}
    results = POST("/storage/volume/tank/datasets/", payload)
    assert results.status_code == 201, results.text


def test_02_Creating_user_testuser():
    payload = {"bsdusr_username": "testuser",
               "bsdusr_creategroup": "true",
               "bsdusr_full_name": "Test User",
               "bsdusr_password": "test",
               "bsdusr_uid": 1111,
               "bsdusr_home": "/mnt/tank/testuser",
               "bsdusr_mode": "755",
               "bsdusr_shell": "/bin/csh"}
    results = POST("/account/users/", payload)
    assert results.status_code == 201, results.text


def test_03_Setting_user_groups_wheel_ftp():
    payload = ["wheel", "ftp"]
    userid = GET_USER("testuser")
    results = POST("/account/users/%s/groups/" % userid, payload)
    assert results.status_code == 202, results.text


# Update tests
# Update the testuser
def test_05_Updating_user_testuser():
    userid = GET_USER("testuser")
    payload = {"bsdusr_username": "testuser",
               "bsdusr_full_name": "Test Renamed",
               "bsdusr_password": "testing123",
               "bsdusr_uid": 1112,
               "bsdusr_home": "/mnt/tank/testuser",
               "bsdusr_mode": "755",
               "bsdusr_shell": "/bin/csh"}
    results = PUT("/account/users/%s/" % userid, payload)
    assert results.status_code == 200, results.text


# Update password for testuser
def test_06_Updating_password_for_testuser():
    userid = GET_USER("testuser")
    payload = {"bsdusr_password": "newpasswd"}
    path = "/account/users/%s/password/" % userid
    results = POST(path, payload)
    assert results.status_code == 200, results.text


# Delete the testuser
def test_08_Deleting_user_testuser():
    userid = GET_USER("testuser")
    results = DELETE("/account/users/%s/" % userid)
    assert results.status_code == 204, results.text
