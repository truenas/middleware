#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, DELETE, PUT
from auto_config import pool_name


# Create tests
def test_01_Creating_home_dataset_testuser():
    payload = {
        "name": "testuser"
    }
    results = POST(f"/storage/volume/{pool_name}/datasets/", payload)
    assert results.status_code == 201, results.text


def test_02_Creating_user_testuser():
    global userid
    payload = {
        "bsdusr_username": "testuser",
        "bsdusr_creategroup": "true",
        "bsdusr_full_name": "Test User",
        "bsdusr_password": "test",
        "bsdusr_uid": 1111,
        "bsdusr_home": f"/mnt/{pool_name}/testuser",
        "bsdusr_mode": "755",
        "bsdusr_shell": "/bin/csh"
    }
    results = POST("/account/users/", payload)
    assert results.status_code == 201, results.text
    userid = results.json()['id']


def test_03_Setting_user_groups_wheel_ftp():
    payload = ["wheel", "ftp"]
    results = POST(f"/account/users/{userid}/groups/", payload)
    assert results.status_code == 202, results.text


# Update tests
# Update the testuser
def test_05_Updating_user_testuser():
    payload = {
        "bsdusr_username": "testuser",
        "bsdusr_full_name": "Test Renamed",
        "bsdusr_password": "testing123",
        "bsdusr_uid": 1112,
        "bsdusr_home": f"/mnt/{pool_name}/testuser",
        "bsdusr_mode": "755",
        "bsdusr_shell": "/bin/csh"
    }
    results = PUT(f"/account/users/{userid}/", payload)
    assert results.status_code == 200, results.text


# Update password for testuser
def test_06_Updating_password_for_testuser():
    payload = {
        "bsdusr_password": "newpasswd"
    }
    path = f"/account/users/{userid}/password/"
    results = POST(path, payload)
    assert results.status_code == 200, results.text


# Delete the testuser
def test_08_Deleting_user_testuser():
    results = DELETE(f"/account/users/{userid}/")
    assert results.status_code == 204, results.text


# Check destroying a SMB dataset
def test_09_Destroying_testuser_dataset():
    results = DELETE(f"/storage/volume/{pool_name}/datasets/testuser/")
    assert results.status_code == 204, results.text
