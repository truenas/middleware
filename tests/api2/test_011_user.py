#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, DELETE, PUT
from auto_config import scale
if scale is True:
    shell = '/bin/bash'
else:
    shell = '/bin/csh'

group = 'root' if scale else 'wheel'
group_id = GET(f'/group/?group={group}').json()[0]['id']


@pytest.mark.dependency(name="user_01")
def test_01_get_next_uid():
    results = GET('/user/get_next_uid/')
    assert results.status_code == 200, results.text
    global next_uid
    next_uid = results.json()


@pytest.mark.dependency(name="user_02")
def test_02_creating_user_testuser(request):
    depends(request, ["user_01"])
    global user_id
    payload = {
        "username": "testuser",
        "full_name": "Test User",
        "group_create": True,
        "password": "test",
        "uid": next_uid,
        "shell": shell
    }
    results = POST("/user/", payload)
    assert results.status_code == 200, results.text
    user_id = results.json()


def test_03_look_user_is_created(request):
    depends(request, ["user_02", "user_01"])
    assert len(GET('/user?username=testuser').json()) == 1


def test_04_get_user_info(request):
    depends(request, ["user_02", "user_01"])
    global userinfo
    userinfo = GET(f'/user/id/{user_id}').json()


def test_05_look_user_name(request):
    depends(request, ["user_02", "user_01"])
    assert userinfo["username"] == "testuser"


def test_06_look_user_full_name(request):
    depends(request, ["user_02", "user_01"])
    assert userinfo["full_name"] == "Test User"


def test_07_look_user_uid(request):
    depends(request, ["user_02", "user_01"])
    assert userinfo["uid"] == next_uid


def test_08_look_user_shell(request):
    depends(request, ["user_02", "user_01"])
    assert userinfo["shell"] == shell


def test_09_add_employee_id_and_team_special_attributes(request):
    depends(request, ["user_02", "user_01"])
    payload = {
        'key': 'Employee ID',
        'value': 'TU1234',
        'key': 'Team',
        'value': 'QA'
    }
    results = POST(f"/user/id/{user_id}/set_attribute/", payload)
    assert results.status_code == 200, results.text


def test_10_get_new_next_uid(request):
    depends(request, ["user_02", "user_01"])
    results = GET('/user/get_next_uid/')
    assert results.status_code == 200, results.text
    global new_next_uid
    new_next_uid = results.json()


def test_11_next_and_new_next_uid_not_equal(request):
    depends(request, ["user_02", "user_01"])
    assert new_next_uid != next_uid


def test_12_setting_user_groups(request):
    depends(request, ["user_02", "user_01"])
    payload = {'groups': [group_id]}
    GET('/user?username=testuser').json()[0]['id']
    results = PUT(f"/user/id/{user_id}/", payload)
    assert results.status_code == 200, results.text


# Update tests
# Update the testuser
def test_13_updating_user_testuser_info(request):
    depends(request, ["user_02", "user_01"])
    payload = {"full_name": "Test Renamed",
               "password": "testing123",
               "uid": new_next_uid}
    results = PUT(f"/user/id/{user_id}/", payload)
    assert results.status_code == 200, results.text


def test_14_get_user_new_info(request):
    depends(request, ["user_02", "user_01"])
    global userinfo
    userinfo = GET('/user?username=testuser').json()[0]


def test_15_look_user_full_name(request):
    depends(request, ["user_02", "user_01"])
    assert userinfo["full_name"] == "Test Renamed"


def test_16_look_user_new_uid(request):
    depends(request, ["user_02", "user_01"])
    assert userinfo["uid"] == new_next_uid


def test_17_look_user_groups(request):
    depends(request, ["user_02", "user_01"])
    assert userinfo["groups"] == [group_id]


def test_18_remove_old_team_special_atribute(request):
    depends(request, ["user_02", "user_01"])
    payload = 'Team'
    results = POST(f"/user/id/{user_id}/pop_attribute/", payload)
    assert results.status_code == 200, results.text


def test_19_add_new_team_to_special_atribute(request):
    depends(request, ["user_02", "user_01"])
    payload = {'key': 'Team', 'value': 'QA'}
    results = POST(f"/user/id/{user_id}/set_attribute/", payload)
    assert results.status_code == 200, results.text


# Delete the testuser
def test_20_deleting_user_testuser(request):
    depends(request, ["user_02", "user_01"])
    results = DELETE(f"/user/id/{user_id}/", {"delete_group": True})
    assert results.status_code == 200, results.text


def test_21_look_user_is_delete(request):
    depends(request, ["user_02", "user_01"])
    assert len(GET('/user?username=testuser').json()) == 0


def test_22_has_root_password(request):
    depends(request, ["user_02", "user_01"])
    assert GET('/user/has_root_password/', anonymous=True).json() is True


def test_23_get_next_uid_for_shareuser(request):
    depends(request, ["user_02", "user_01"])
    results = GET('/user/get_next_uid/')
    assert results.status_code == 200, results.text
    global next_uid
    next_uid = results.json()


@pytest.mark.dependency(name="user_24")
def test_24_creating_shareuser_to_test_sharing(request):
    depends(request, ["user_02", "user_01"])
    payload = {
        "username": "shareuser",
        "full_name": "Share User",
        "group_create": True,
        "groups": [group_id],
        "password": "testing",
        "uid": next_uid,
        "shell": shell
    }
    results = POST("/user/", payload)
    assert results.status_code == 200, results.text
