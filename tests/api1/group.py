#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, PUT, DELETE, SSH_TEST
from auto_config import user, password, ip
GroupIdFile = "/tmp/.ixbuild_test_groupid"


# Create tests
def test_01_Creating_group_testgroup():
    global groupid
    payload = {
        "bsdgrp_gid": 1200,
        "bsdgrp_group": "testgroup"
    }
    results = POST("/account/groups/", payload)
    assert results.status_code == 201, results.text
    groupid = results.json()['id']


def test_02_look_for_testgroup_is_in_freenas_group():
    cmd = 'getent group | grep -q testgroup'
    results = SSH_TEST(cmd, 'root', 'testing', ip)
    assert results['result'] is True, results['output']


# Update the testgroup
def test_03_Updating_group_testgroup():
    payload = {
        "bsdgrp_gid": "1201",
        "bsdgrp_group": "newgroup"
    }
    results = PUT(f"/account/groups/{groupid}/", payload)
    assert results.status_code == 200, results.text


def test_04_look_for_testgroup_is_not_in_freenas_group():
    cmd = 'getent group | grep -q testgroup'
    results = SSH_TEST(cmd, 'root', 'testing', ip)
    assert results['result'] is False, results['output']


def test_05_look_for_newgroup_is_in_freenas_group():
    cmd = 'getent group | grep -q newgroup'
    results = SSH_TEST(cmd, 'root', 'testing', ip)
    assert results['result'] is True, results['output']


# Delete tests
# Delete the testgroup
def test_06_Delete_group_testgroup_newgroup():
    results = DELETE(f"/account/groups/{groupid}/")
    assert results.status_code == 204, results.text

def test_07_look_for_newgroup_is_not_in_freenas_group():
    cmd = 'getent group | grep -q newgroup'
    results = SSH_TEST(cmd, 'root', 'testing', ip)
    assert results['result'] is False, results['output']
