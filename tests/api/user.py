#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, DELETE, PUT


def test_01_get_next_uid():
    results = GET('/user/get_next_uid/')
    assert results.status_code == 200, results.text
    global next_uid
    next_uid = results.json()


def test_02_creating_user_testuser():
    payload = {"username": "testuser",
               "full_name": "Test User",
               "group_create": True,
               "password": "test",
               "uid": next_uid,
               "shell": "/bin/csh"}
    results = POST("/user/", payload)
    assert results.status_code == 200, results.text


def test_03_look_user_is_created():
    assert len(GET('/user?username=testuser').json()) == 1


def test_04_get_user_info():
    global userinfo
    userinfo = GET('/user?username=testuser').json()[0]


def test_05_look_user_name():
    assert userinfo["username"] == "testuser"


def test_06_look_user_full_name():
    assert userinfo["full_name"] == "Test User"


def test_07_look_user_uid():
    assert userinfo["uid"] == next_uid


def test_08_look_user_shell():
    assert userinfo["shell"] == "/bin/csh"


def test_09_add_employe_id_and_team_special_atributes():
    userid = GET('/user?username=testuser').json()[0]['id']
    payload = {'key': 'Employe ID', 'value': 'TU1234',
               'key': 'Team', 'value': 'QA'}
    results = POST("/user/id/%s/set_attribute" % userid, payload)
    assert results.status_code == 200, results.text


def test_10_get_new_next_uid():
    results = GET('/user/get_next_uid/')
    assert results.status_code == 200, results.text
    global new_next_uid
    new_next_uid = results.json()


def test_11_next_and_new_next_uid_not_equal():
    assert new_next_uid != next_uid


def test_12_setting_user_groups():
    userid = GET('/user?username=testuser').json()[0]['id']
    payload = {'groups': [1]}
    GET('/user?username=testuser').json()[0]['id']
    results = PUT("/user/id/%s" % userid, payload)
    assert results.status_code == 200, results.text


# Update tests
# Update the testuser
def test_13_updating_user_testuser_info():
    userid = GET('/user?username=testuser').json()[0]['id']
    payload = {"full_name": "Test Renamed",
               "password": "testing123",
               "uid": new_next_uid}
    results = PUT("/user/id/%s" % userid, payload)
    assert results.status_code == 200, results.text


def test_14_get_user_new_info():
    global userinfo
    userinfo = GET('/user?username=testuser').json()[0]


def test_15_look_user_full_name():
    assert userinfo["full_name"] == "Test Renamed"


def test_16_look_user_new_uid():
    assert userinfo["uid"] == new_next_uid


def test_17_look_user_groups():
    assert userinfo["groups"] == [1]


def test_18_remove_old_team_special_atribute():
    userid = GET('/user?username=testuser').json()[0]['id']
    payload = 'Team'
    results = POST("/user/id/%s/pop_attribute/" % userid, payload)
    assert results.status_code == 200, results.text


def test_19_add_new_team_to_special_atribute():
    userid = GET('/user?username=testuser').json()[0]['id']
    payload = {'key': 'Team', 'value': 'QA'}
    results = POST("/user/id/%s/set_attribute/" % userid, payload)
    assert results.status_code == 200, results.text


# Delete the testuser
def test_20_deleting_user_testuser():
    userid = GET('/user?username=testuser').json()[0]['id']
    results = DELETE("/user/id/%s/" % userid, {"delete_group": True})
    assert results.status_code == 200, results.text


def test_21_look_user_is_delete():
    assert len(GET('/user?username=testuser').json()) == 0


def test_22_has_root_password():
    assert GET('/user/has_root_password/', anonymous=True).json() is True
