#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os
import json
import pytest
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT, DELETE, SSH_TEST
from auto_config import user, password
from middlewared.test.integration.utils import call
from pytest_dependency import depends


def test_01_get_next_gid():
    results = GET('/group/get_next_gid/')
    assert results.status_code == 200, results.text
    global next_gid
    next_gid = results.json()


# Create tests
def test_02_creating_group_testgroup():
    global groupid
    payload = {
        "gid": next_gid,
        "name": "testgroup",
        "smb": False,
    }
    results = POST("/group/", payload)
    assert results.status_code == 200, results.text
    groupid = results.json()


def test_03_look_group_is_created():
    assert len(GET('/group?group=testgroup').json()) == 1


def test_04_check_group_exists():
    """
    get_group_obj is a wrapper around the grp module.
    This check verifies that the group is _actually_ created.
    """
    payload = {
        "groupname": "testgroup"
    }
    results = POST("/group/get_group_obj/", payload)
    assert results.status_code == 200, results.text
    if results.status_code == 200:
        gr = results.json()
        assert gr['gr_gid'] == next_gid, results.text


def test_05_get_group_info():
    global groupinfo
    groupinfo = GET('/group?group=testgroup').json()[0]


def test_06_look_group_name():
    assert groupinfo["group"] == "testgroup"


def test_07_look_group_full_name():
    assert groupinfo["gid"] == next_gid


def test_08_look_for_testgroup_is_in_freenas_group(request):
    result = GET(
        '/group', payload={
            'query-filters': [['name', '=', 'testgroup']],
            'query-options': {
                'get': True,
                'extra': {'additional_information': ['SMB']}
            }
        }
    )
    assert result.status_code == 200, result.text
    assert result.json()['sid'] is None, result.text


def test_09_get_new_next_gid():
    results = GET('/group/get_next_gid/')
    assert results.status_code == 200, results.text
    global new_next_gid
    new_next_gid = results.json()


def test_10_next_gid_and_new_next_gid_not_equal():
    assert new_next_gid != next_gid


# Update the testgroup
def test_11_updating_group_testgroup():
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


def test_15_look_for_testgroup_is_not_in_freenas_group(request):
    payload = {
        "groupname": "testgroup"
    }
    results = POST("/group/get_group_obj/", payload)
    assert results.status_code == 500, results.text


def test_16_look_for_newgroup_is_in_freenas_group(request):
    payload = {
        "groupname": "newgroup"
    }
    results = POST("/group/get_group_obj/", payload)
    assert results.status_code == 200, results.text


# Delete the group
def test_19_delete_group_testgroup_newgroup():
    results = DELETE(f"/group/id/{groupid}/", {"delete_users": True})
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('group', [
    {"root": 0},
    {"wheel": 0},
    {"nogroup": 65534},
    {"nobody": 65534}
])
def test_35_check_builtin_groups(group):
    """
    This check verifies the existence of targeted built-in groups
    """
    g_name, g_id = list(group.items())[0]
    gr = call("group.get_group_obj", {"groupname": g_name})
    assert gr['gr_gid'] == g_id, f"{g_name}:  expected gid {g_id}, but got {gr['gr_gid']}"


@pytest.mark.parametrize('nss_obj', [
    ('group', 'root', 0),
    ('group', 'nogroup', 65534)
])
def test_36_check_builtin_duplicate_id_order(nss_obj):
    # For compatibility with FreeBSD-based SCALE versions we
    # map "wheel" to gid 0 and "nogroup" to gid 65534. This validate
    # lookups by gid to return expected Linux names.
    nss_type, name, xid = nss_obj
    if nss_type == "group":
        xid_key = "gid"
        name_key = "gr_name"
    else:
        xid_key = "uid"
        name_key = "pw_name"

    obj = call(f"{nss_type}.get_{nss_type}_obj", {xid_key: xid})
    assert obj[name_key] == name
