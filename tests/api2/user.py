#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import json
import os
import time
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, DELETE, PUT, SSH_TEST, wait_on_job
from auto_config import pool_name, password, user, ip
shell = '/bin/csh'
from pytest_dependency import depends

dataset = f"{pool_name}/test_homes"
dataset_url = dataset.replace('/', '%2F')

home_files = {
    "~/": "0o40750",
    "~/.profile": "0o100644",
    "~/.ssh": "0o40700",
    "~/.ssh/authorized_keys": "0o100600",
}

home_acl = [
    {
        "tag": "owner@",
        "id": None,
        "type": "ALLOW",
        "perms": {"BASIC": "FULL_CONTROL"},
        "flags": {"BASIC": "INHERIT"}
    },
    {
        "tag": "group@",
        "id": None,
        "type": "ALLOW",
        "perms": {"BASIC": "FULL_CONTROL"},
        "flags": {"BASIC": "INHERIT"}
    },
    {
        "tag": "everyone@",
        "id": None,
        "type": "ALLOW",
        "perms": {"BASIC": "TRAVERSE"},
        "flags": {"BASIC": "NOINHERIT"}
    },
]


def test_01_get_next_uid():
    results = GET('/user/get_next_uid/')
    assert results.status_code == 200, results.text
    global next_uid
    next_uid = results.json()


def test_02_creating_user_testuser():
    payload = {"username": "testuser",
               "full_name": "Test User",
               "group_create": True,
               "password": "test1234",
               "uid": next_uid,
               "shell": "/bin/csh"}
    results = POST("/user/", payload)
    assert results.status_code == 200, results.text


def test_03_verify_post_user_do_not_leak_password_in_middleware_log():
    cmd = """grep -R "test1234" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_04_look_user_is_created():
    assert len(GET('/user?username=testuser').json()) == 1


def test_05_get_user_info():
    global userinfo
    userinfo = GET('/user?username=testuser').json()[0]


def test_06_look_user_name():
    assert userinfo["username"] == "testuser"


def test_07_look_user_full_name():
    assert userinfo["full_name"] == "Test User"


def test_08_look_user_uid():
    assert userinfo["uid"] == next_uid


def test_09_look_user_shell():
    assert userinfo["shell"] == "/bin/csh"


def test_10_add_employe_id_and_team_special_atributes():
    userid = GET('/user?username=testuser').json()[0]['id']
    payload = {'key': 'Employe ID', 'value': 'TU1234',
               'key': 'Team', 'value': 'QA'}
    results = POST("/user/id/%s/set_attribute" % userid, payload)
    assert results.status_code == 200, results.text


def test_11_get_new_next_uid():
    results = GET('/user/get_next_uid/')
    assert results.status_code == 200, results.text
    global new_next_uid
    new_next_uid = results.json()


def test_12_next_and_new_next_uid_not_equal():
    assert new_next_uid != next_uid


def test_13_setting_user_groups():
    userid = GET('/user?username=testuser').json()[0]['id']
    payload = {'groups': [1]}
    GET('/user?username=testuser').json()[0]['id']
    results = PUT("/user/id/%s" % userid, payload)
    assert results.status_code == 200, results.text


# Update tests
# Update the testuser
def test_14_updating_user_testuser_info():
    userid = GET('/user?username=testuser').json()[0]['id']
    payload = {"full_name": "Test Renamed",
               "password": "testing123",
               "uid": new_next_uid}
    results = PUT("/user/id/%s" % userid, payload)
    assert results.status_code == 200, results.text


def test_15_verify_put_user_do_not_leak_password_in_middleware_log():
    cmd = """grep -R "testing123" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_16_get_user_new_info():
    global userinfo
    userinfo = GET('/user?username=testuser').json()[0]


def test_17_look_user_full_name():
    assert userinfo["full_name"] == "Test Renamed"


def test_18_look_user_new_uid():
    assert userinfo["uid"] == new_next_uid


def test_19_look_user_groups():
    assert userinfo["groups"] == [1]


def test_20_remove_old_team_special_atribute():
    userid = GET('/user?username=testuser').json()[0]['id']
    payload = 'Team'
    results = POST("/user/id/%s/pop_attribute/" % userid, payload)
    assert results.status_code == 200, results.text


def test_21_add_new_team_to_special_atribute():
    userid = GET('/user?username=testuser').json()[0]['id']
    payload = {'key': 'Team', 'value': 'QA'}
    results = POST("/user/id/%s/set_attribute/" % userid, payload)
    assert results.status_code == 200, results.text


# Delete the testuser
def test_22_deleting_user_testuser():
    userid = GET('/user?username=testuser').json()[0]['id']
    results = DELETE("/user/id/%s/" % userid, {"delete_group": True})
    assert results.status_code == 200, results.text


def test_23_look_user_is_delete():
    assert len(GET('/user?username=testuser').json()) == 0


def test_24_has_root_password():
    assert GET('/user/has_root_password/', anonymous=True).json() is True


def test_25_get_next_uid_for_shareuser():
    results = GET('/user/get_next_uid/')
    assert results.status_code == 200, results.text
    global next_uid
    next_uid = results.json()


def test_26_creating_shareuser_to_test_sharing():
    payload = {
        "username": "shareuser",
        "full_name": "Share User",
        "group_create": True,
        "groups": [1],
        "password": "testing",
        "uid": next_uid,
        "shell": "/bin/csh"}
    results = POST("/user/", payload)
    assert results.status_code == 200, results.text


def test_27_verify_post_user_do_not_leak_password_in_middleware_log():
    cmd = """grep -R "testing" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_28_get_next_uid_for_homes_check():
    results = GET('/user/get_next_uid/')
    assert results.status_code == 200, results.text
    global next_uid
    next_uid = results.json()


@pytest.mark.dependency(name="HOME_DS_CREATED")
def test_29_creating_home_dataset():
    """
    SMB share_type is selected for this test so that
    we verify that ACL is being stripped properly from
    the newly-created home directory.
    Separate call to set an ACL is required in order
    to allow TRAVERSE rights.
    """
    payload = {
        "name": dataset,
        "share_type": "SMB"
    }
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text

    results = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': home_acl,
        }
    )
    assert results.status_code == 200, results.text
    perm_job = results.json()
    job_status = wait_on_job(perm_job, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@pytest.mark.dependency(name="USER_CREATED")
def test_30_creating_user_with_homedir(request):
    depends(request, ["HOME_DS_CREATED"])
    global user_id
    payload = {
        "username": "testuser2",
        "full_name": "Test User2",
        "group_create": True,
        "password": "test1234",
        "uid": next_uid,
        "shell": shell,
        "sshpubkey": "canary",
        "home": f'/mnt/{dataset}/testuser2',
        "home_mode": '750'
    }
    results = POST("/user/", payload)
    assert results.status_code == 200, results.text
    user_id = results.json()


def test_31_verify_post_user_do_not_leak_password_in_middleware_log(request):
    depends(request, ["USER_CREATED"])
    cmd = """grep -R "test1234" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_32_smb_user_passb_entry_exists(request):
    depends(request, ["USER_CREATED"])
    cmd = "midclt call smb.passdb_list true"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    pdb_list = json.loads(results['output'])
    my_entry = None
    for entry in pdb_list:
        if entry['Unix username'] == "testuser2":
            my_entry = entry
            break

    assert my_entry is not None, results['output']
    if my_entry is not None:
        assert my_entry["Account Flags"] == "[U          ]", str(my_entry)


@pytest.mark.dependency(name="HOMEDIR_EXISTS")
def test_33_homedir_exists(request):
    depends(request, ["USER_CREATED"])
    results = POST('/filesystem/stat/', f'/mnt/{dataset}/testuser2')
    assert results.status_code == 200, results.text


def test_34_homedir_acl_stripped(request):
    depends(request, ["HOMEDIR_EXISTS"])
    # Homedir permissions changes are backgrounded.
    # one second sleep should be sufficient for them to complete.
    time.sleep(1)
    results = POST('/filesystem/stat/', f'/mnt/{dataset}/testuser2')
    assert results.status_code == 200, results.text
    assert results.json()['acl'] is False, results.text


@pytest.mark.parametrize('to_test', home_files.keys())
def test_35_homedir_check_perm(to_test, request):
    depends(request, ["HOMEDIR_EXISTS"])
    results = POST('/filesystem/stat/', f'/mnt/{dataset}/testuser2/{to_test[2:]}')
    assert results.status_code == 200, results.text
    assert oct(results.json()['mode']) == home_files[to_test], f"{to_test}: {results.text}"
    assert results.json()['uid'] == next_uid, results.text


def test_36_homedir_testfile_create(request):
    depends(request, ["HOMEDIR_EXISTS"])
    testfile = f'/mnt/{dataset}/testuser2/testfile.txt'

    cmd = f'touch {testfile}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    results = POST('/filesystem/stat/', testfile)
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="HOMEDIR2_EXISTS")
def test_37_homedir_move_new_directory(request):
    depends(request, ["HOMEDIR_EXISTS"])
    payload = {
        "home": f'/mnt/{dataset}/new_home',
    }
    results = PUT(f"/user/id/{user_id}", payload)
    assert results.status_code == 200, results.text

    results = POST('/filesystem/stat/', f'/mnt/{dataset}/new_home')
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('to_test', home_files.keys())
def test_38_after_move_check_perm(to_test, request):
    depends(request, ["HOMEDIR2_EXISTS"])
    results = POST('/filesystem/stat/', f'/mnt/{dataset}/new_home/{to_test[2:]}')
    assert results.status_code == 200, results.text
    assert oct(results.json()['mode']) == home_files[to_test], f"{to_test}: {results.text}"
    assert results.json()['uid'] == next_uid, results.text


def test_39_testfile_successfully_moved(request):
    depends(request, ["HOMEDIR2_EXISTS"])
    results = POST('/filesystem/stat/', f'/mnt/{dataset}/new_home/testfile.txt')
    assert results.status_code == 200, results.text


def test_40_lock_smb_user(request):
    depends(request, ["USER_CREATED"])
    payload = {
        "locked": True,
    }
    results = PUT(f"/user/id/{user_id}", payload)
    assert results.status_code == 200, results.text


def test_41_verify_locked_smb_user_is_disabled(request):
    depends(request, ["USER_CREATED"])
    cmd = "midclt call smb.passdb_list true"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    pdb_list = json.loads(results['output'])
    my_entry = None
    for entry in pdb_list:
        if entry['Unix username'] == "testuser2":
            my_entry = entry
            break

    assert my_entry is not None, results['output']
    if my_entry is not None:
        assert my_entry["Account Flags"] == "[DU         ]", str(my_entry)


def test_42_deleting_homedir_user(request):
    depends(request, ["USER_CREATED"])
    results = DELETE(f"/user/id/{user_id}/", {"delete_group": True})
    assert results.status_code == 200, results.text


def test_43_destroying_home_dataset(request):
    depends(request, ["HOME_DS_CREATED"])
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
