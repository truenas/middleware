#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT, DELETE

GroupIdFile = "/tmp/.ixbuild_test_groupid"


def test_01_get_next_gid():
    results = GET('/group/get_next_gid/')
    assert results.status_code == 200, results.text
    global next_gid
    next_gid = results.json()


# Create tests
def test_02_greating_group_testgroup():
    payload = {"gid": next_gid, "name": "testgroup"}
    results = POST("/group/", payload)
    assert results.status_code == 200, results.text


def test_03_look_group_is_created():
    assert len(GET('/group?group=testgroup').json()) == 1


def test_04_get_group_info():
    global groupinfo
    groupinfo = GET('/group?group=testgroup').json()[0]


def test_05_look_group_name():
    assert groupinfo["group"] == "testgroup"


def test_06_look_group_full_name():
    assert groupinfo["gid"] == next_gid


def test_07_get_new_next_gid():
    results = GET('/group/get_next_gid/')
    assert results.status_code == 200, results.text
    global new_next_gid
    new_next_gid = results.json()


def test_08_next_gid_and_new_next_gid_not_equal():
    assert new_next_gid != next_gid


# Update the testgroup
def test_09_udating_group_testgroup():
    groupid = GET('/group?group=testgroup').json()[0]['id']
    payload = {"gid": new_next_gid,
               "name": "newgroup"}
    results = PUT("/group/id/%s" % groupid, payload)
    assert results.status_code == 200, results.text


def test_10_get_group_new_info():
    global groupinfo
    groupinfo = GET('/group?group=newgroup').json()[0]


def test_11_look_group_name():
    assert groupinfo["group"] == "newgroup"


def test_12_look_user_new_uid():
    assert groupinfo["gid"] == new_next_gid


# Delete the group
def test_13_delete_group_testgroup_newgroup():
    groupid = GET('/group?group=newgroup').json()[0]['id']
    results = DELETE("/group/id/%s/" % groupid, {"delete_users": True})
    assert results.status_code == 200, results.text


def test_14_look_group_is_delete():
    assert len(GET('/group?group=newuser').json()) == 0
