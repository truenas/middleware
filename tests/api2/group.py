#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT, DELETE, SSH_TEST
from auto_config import user, password, ip

GroupIdFile = "/tmp/.ixbuild_test_groupid"


def test_01_get_next_gid():
    results = GET('/group/get_next_gid/')
    assert results.status_code == 200, results.text
    global next_gid
    next_gid = results.json()


# Create tests
def test_02_greating_group_testgroup():
    global groupid
    payload = {
        "gid": next_gid,
        "name": "testgroup"
    }
    results = POST("/group/", payload)
    assert results.status_code == 200, results.text
    groupid = results.json()


def test_03_look_group_is_created():
    assert len(GET('/group?group=testgroup').json()) == 1


def test_04_get_group_info():
    global groupinfo
    groupinfo = GET('/group?group=testgroup').json()[0]


def test_05_look_group_name():
    assert groupinfo["group"] == "testgroup"


def test_06_look_group_full_name():
    assert groupinfo["gid"] == next_gid


def test_07_look_for_testgroup_is_in_freenas_group():
    cmd = 'getent group | grep -q testgroup'
    results = SSH_TEST(cmd, 'root', 'testing', ip)
    assert results['result'] is True, results['output']


def test_08_get_new_next_gid():
    results = GET('/group/get_next_gid/')
    assert results.status_code == 200, results.text
    global new_next_gid
    new_next_gid = results.json()


def test_09_next_gid_and_new_next_gid_not_equal():
    assert new_next_gid != next_gid


# Update the testgroup
def test_10_udating_group_testgroup():
    payload = {
        "gid": new_next_gid,
        "name": "newgroup"
    }
    results = PUT("/group/id/%s" % groupid, payload)
    assert results.status_code == 200, results.text


def test_12_get_group_new_info():
    global groupinfo
    groupinfo = GET('/group?group=newgroup').json()[0]


def test_13_look_group_name():
    assert groupinfo["group"] == "newgroup"


def test_14_look_user_new_uid():
    assert groupinfo["gid"] == new_next_gid


def test_15_look_for_testgroup_is_not_in_freenas_group():
    cmd = 'getent group | grep -q testgroup'
    results = SSH_TEST(cmd, 'root', 'testing', ip)
    assert results['result'] is False, results['output']


def test_16_look_for_newgroup_is_in_freenas_group():
    cmd = 'getent group | grep -q newgroup'
    results = SSH_TEST(cmd, 'root', 'testing', ip)
    assert results['result'] is True, results['output']

# Delete the group
def test_17_delete_group_testgroup_newgroup():
    results = DELETE(f"/group/id/{groupid}/", {"delete_users": True})
    assert results.status_code == 200, results.text


def test_18_look_group_is_delete():
    assert len(GET('/group?group=newuser').json()) == 0


def test_19_look_for_newgroup_is_not_in_freenas_group():
    cmd = 'getent group | grep -q newgroup'
    results = SSH_TEST(cmd, 'root', 'testing', ip)
    assert results['result'] is False, results['output']
