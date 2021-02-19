#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import json
import os
import time
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, DELETE, PUT, SSH_TEST, wait_on_job
from auto_config import pool_name, scale, ha, password, user, ip
if scale is True:
    shell = '/usr/bin/bash'
else:
    shell = '/bin/csh'

group = 'root' if scale else 'wheel'
group_id = GET(f'/group/?group={group}', controller_a=ha).json()[0]['id']

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


@pytest.mark.dependency(name="user_01")
def test_01_get_next_uid(request):
    results = GET('/user/get_next_uid/')
    assert results.status_code == 200, results.text
    global next_uid
    next_uid = results.json()


@pytest.mark.dependency(name="user_02")
def test_02_creating_user_testuser(request):
    depends(request, ["user_01"])
    """
    Test for basic user creation. In this case 'smb' is disabled to bypass
    passdb-related code. This is because the passdb add relies on users existing
    in passwd database, and errors during error creation will get masked as
    passdb errors.
    """
    global user_id
    payload = {
        "username": "testuser",
        "full_name": "Test User",
        "group_create": True,
        "password": "test1234",
        "uid": next_uid,
        "smb": False,
        "shell": shell
    }
    results = POST("/user/", payload)
    assert results.status_code == 200, results.text
    user_id = results.json()


def test_03_verify_post_user_do_not_leak_password_in_middleware_log(request):
    depends(request, ["user_01", "ssh_password"], scope="session")
    cmd = """grep -R "test1234" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_04_look_user_is_created(request):
    depends(request, ["user_02", "user_01"])
    assert len(GET('/user?username=testuser').json()) == 1


def test_05_check_user_exists(request):
    """
    get_user_obj is a wrapper around the pwd module.
    This check verifies that the user is _actually_ created.
    """
    payload = {
        "username": "testuser"
    }
    results = POST("/user/get_user_obj/", payload)
    assert results.status_code == 200, results.text
    if results.status_code == 200:
        pw = results.json()
        assert pw['pw_uid'] == next_uid, results.text
        assert pw['pw_shell'] == shell, results.text


def test_06_get_user_info(request):
    depends(request, ["user_02", "user_01"])
    global userinfo
    userinfo = GET(f'/user/id/{user_id}').json()


def test_07_look_user_name(request):
    depends(request, ["user_02", "user_01"])
    assert userinfo["username"] == "testuser"


def test_08_look_user_full_name(request):
    depends(request, ["user_02", "user_01"])
    assert userinfo["full_name"] == "Test User"


def test_09_look_user_uid(request):
    depends(request, ["user_02", "user_01"])
    assert userinfo["uid"] == next_uid


def test_10_look_user_shell(request):
    depends(request, ["user_02", "user_01"])
    assert userinfo["shell"] == shell


def test_11_add_employee_id_and_team_special_attributes(request):
    depends(request, ["user_02", "user_01"])
    payload = {
        'key': 'Employee ID',
        'value': 'TU1234',
        'key': 'Team',
        'value': 'QA'
    }
    results = POST(f"/user/id/{user_id}/set_attribute/", payload)
    assert results.status_code == 200, results.text


def test_12_get_new_next_uid(request):
    depends(request, ["user_02", "user_01"])
    results = GET('/user/get_next_uid/')
    assert results.status_code == 200, results.text
    global new_next_uid
    new_next_uid = results.json()


def test_13_next_and_new_next_uid_not_equal(request):
    depends(request, ["user_02", "user_01"])
    assert new_next_uid != next_uid


def test_14_setting_user_groups(request):
    depends(request, ["user_02", "user_01"])
    payload = {'groups': [group_id]}
    GET('/user?username=testuser').json()[0]['id']
    results = PUT(f"/user/id/{user_id}/", payload)
    assert results.status_code == 200, results.text


# Update tests
# Update the testuser
def test_15_updating_user_testuser_info(request):
    depends(request, ["user_02", "user_01"])
    payload = {"full_name": "Test Renamed",
               "password": "testing123",
               "uid": new_next_uid}
    results = PUT(f"/user/id/{user_id}/", payload)
    assert results.status_code == 200, results.text


def test_16_verify_put_user_do_not_leak_password_in_middleware_log(request):
    depends(request, ["user_02", "user_01", "ssh_password"], scope="session")
    cmd = """grep -R "testing123" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_17_get_user_new_info(request):
    depends(request, ["user_02", "user_01"])
    global userinfo
    userinfo = GET('/user?username=testuser').json()[0]


def test_18_look_user_full_name(request):
    depends(request, ["user_02", "user_01"])
    assert userinfo["full_name"] == "Test Renamed"


def test_19_look_user_new_uid(request):
    depends(request, ["user_02", "user_01"])
    assert userinfo["uid"] == new_next_uid


def test_20_look_user_groups(request):
    depends(request, ["user_02", "user_01"])
    assert userinfo["groups"] == [group_id]


def test_21_remove_old_team_special_atribute(request):
    depends(request, ["user_02", "user_01"])
    payload = 'Team'
    results = POST(f"/user/id/{user_id}/pop_attribute/", payload)
    assert results.status_code == 200, results.text


def test_22_add_new_team_to_special_atribute(request):
    depends(request, ["user_02", "user_01"])
    payload = {'key': 'Team', 'value': 'QA'}
    results = POST(f"/user/id/{user_id}/set_attribute/", payload)
    assert results.status_code == 200, results.text


# Delete the testuser
def test_23_deleting_user_testuser(request):
    depends(request, ["user_02", "user_01"])
    results = DELETE(f"/user/id/{user_id}/", {"delete_group": True})
    assert results.status_code == 200, results.text


def test_24_look_user_is_delete(request):
    depends(request, ["user_02", "user_01"])
    assert len(GET('/user?username=testuser').json()) == 0


def test_25_has_root_password(request):
    depends(request, ["user_02", "user_01"])
    assert GET('/user/has_root_password/', anonymous=True).json() is True


def test_26_get_next_uid_for_shareuser(request):
    depends(request, ["user_02", "user_01"])
    results = GET('/user/get_next_uid/')
    assert results.status_code == 200, results.text
    global next_uid
    next_uid = results.json()


@pytest.mark.dependency(name="shareuser")
def test_27_creating_shareuser_to_test_sharing(request):
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


def test_28_verify_post_user_do_not_leak_password_in_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "testing" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_29_get_next_uid_for_homes_check(request):
    results = GET('/user/get_next_uid/')
    assert results.status_code == 200, results.text
    global next_uid
    next_uid = results.json()


@pytest.mark.dependency(name="HOME_DS_CREATED")
def test_30_creating_home_dataset(request):
    """
    SMB share_type is selected for this test so that
    we verify that ACL is being stripped properly from
    the newly-created home directory.
    """
    depends(request, ["pool_04"], scope="session")
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
def test_31_creating_user_with_homedir(request):
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
    time.sleep(2)


def test_32_verify_post_user_do_not_leak_password_in_middleware_log(request):
    depends(request, ["USER_CREATED", "ssh_password"], scope="session")
    cmd = """grep -R "test1234" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_33_smb_user_passb_entry_exists(request):
    depends(request, ["USER_CREATED", "ssh_password"], scope="session")
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
def test_34_homedir_exists(request):
    depends(request, ["USER_CREATED"])
    results = POST('/filesystem/stat/', f'/mnt/{dataset}/testuser2')
    assert results.status_code == 200, results.text


def test_35_homedir_acl_stripped(request):
    depends(request, ["HOMEDIR_EXISTS"])
    # Homedir permissions changes are backgrounded.
    # one second sleep should be sufficient for them to complete.
    time.sleep(1)
    results = POST('/filesystem/stat/', f'/mnt/{dataset}/testuser2')
    assert results.status_code == 200, results.text
    assert results.json()['acl'] is False, results.text


@pytest.mark.parametrize('to_test', home_files.keys())
def test_36_homedir_check_perm(to_test, request):
    depends(request, ["HOMEDIR_EXISTS"])
    results = POST('/filesystem/stat/', f'/mnt/{dataset}/testuser2/{to_test[2:]}')
    assert results.status_code == 200, results.text
    assert oct(results.json()['mode']) == home_files[to_test], f"{to_test}: {results.text}"
    assert results.json()['uid'] == next_uid, results.text


def test_37_homedir_testfile_create(request):
    depends(request, ["HOMEDIR_EXISTS", "ssh_password"], scope="session")
    testfile = f'/mnt/{dataset}/testuser2/testfile.txt'

    cmd = f'touch {testfile}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    results = POST('/filesystem/stat/', testfile)
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="HOMEDIR2_EXISTS")
def test_38_homedir_move_new_directory(request):
    depends(request, ["HOMEDIR_EXISTS"])
    payload = {
        "home": f'/mnt/{dataset}/new_home',
    }
    results = PUT(f"/user/id/{user_id}", payload)
    assert results.status_code == 200, results.text

    results = POST('/filesystem/stat/', f'/mnt/{dataset}/new_home')
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('to_test', home_files.keys())
def test_39_after_move_check_perm(to_test, request):
    depends(request, ["HOMEDIR2_EXISTS"])
    results = POST('/filesystem/stat/', f'/mnt/{dataset}/new_home/{to_test[2:]}')
    assert results.status_code == 200, results.text
    assert oct(results.json()['mode']) == home_files[to_test], f"{to_test}: {results.text}"
    assert results.json()['uid'] == next_uid, results.text


def test_40_testfile_successfully_moved(request):
    depends(request, ["HOMEDIR2_EXISTS"])
    results = POST('/filesystem/stat/', f'/mnt/{dataset}/new_home/testfile.txt')
    assert results.status_code == 200, results.text


def test_41_lock_smb_user(request):
    depends(request, ["USER_CREATED"])
    payload = {
        "locked": True,
    }
    results = PUT(f"/user/id/{user_id}", payload)
    assert results.status_code == 200, results.text
    time.sleep(2)


def test_42_verify_locked_smb_user_is_disabled(request):
    """
    This test verifies that the passdb user is disabled
    when "locked" is set to True.
    """
    depends(request, ["USER_CREATED", "ssh_password"], scope="session")
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


def test_43_convert_to_non_smb_user(request):
    depends(request, ["USER_CREATED"])
    payload = {
        "smb": False,
    }
    results = PUT(f"/user/id/{user_id}", payload)
    assert results.status_code == 200, results.text


def test_44_verify_absent_from_passdb(request):
    """
    This test verifies that the user no longer appears
    in Samba's passdb after "smb" is set to False.
    """
    depends(request, ["USER_CREATED", "ssh_password"], scope="session")
    cmd = "midclt call smb.passdb_list true"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    pdb_list = json.loads(results['output'])
    my_entry = None
    for entry in pdb_list:
        if entry['Unix username'] == "testuser2":
            my_entry = entry
            break

    assert my_entry is None, results['output']


def test_45_deleting_homedir_user(request):
    depends(request, ["USER_CREATED"])
    results = DELETE(f"/user/id/{user_id}/", {"delete_group": True})
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="NON_SMB_USER_CREATED")
def test_46_creating_non_smb_user(request):
    depends(request, ["HOME_DS_CREATED"])
    global user_id
    payload = {
        "username": "testuser3",
        "full_name": "Test User3",
        "group_create": True,
        "password": "testabcd",
        "uid": next_uid,
        "smb": False
    }
    results = POST("/user/", payload)
    assert results.status_code == 200, results.text
    user_id = results.json()


def test_47_verify_post_user_do_not_leak_password_in_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "testabcd" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_48_verify_non_smb_user_absent_from_passdb(request):
    """
    Creating new user with "smb" = False must not
    result in a passdb entry being generated.
    """
    depends(request, ["NON_SMB_USER_CREATED", "ssh_password"], scope="session")
    cmd = "midclt call smb.passdb_list true"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    pdb_list = json.loads(results['output'])
    my_entry = None
    for entry in pdb_list:
        if entry['Unix username'] == "testuser3":
            my_entry = entry
            break

    assert my_entry is None, results['output']


def test_49_convert_to_smb_knownfail(request):
    """
    SMB auth for local users relies stored NT hash. We only generate this hash
    for SMB users. This means that converting from non-SMB to SMB requires
    re-submitting password so that we can generate the required hash. If
    payload submitted without password, then validation error _must_ be raised.
    """
    depends(request, ["NON_SMB_USER_CREATED"])
    payload = {
        "smb": True,
    }
    results = PUT(f"/user/id/{user_id}", payload)
    assert results.status_code == 422, results.text


def test_50_convert_to_smb_user(request):
    depends(request, ["NON_SMB_USER_CREATED"])
    payload = {
        "smb": True,
        "password": "testabcd1234",
    }
    results = PUT(f"/user/id/{user_id}", payload)
    assert results.status_code == 200, results.text
    time.sleep(2)


def test_51_verify_put_user_do_not_leak_password_in_middleware_log(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = """grep -R "testabcd1234" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_52_converted_smb_user_passb_entry_exists(request):
    """
    At this point the non-SMB user has been converted to an SMB user. Verify
    that a passdb entry was appropriately generated.
    """
    depends(request, ["NON_SMB_USER_CREATED", "ssh_password"], scope="session")
    cmd = "midclt call smb.passdb_list true"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    pdb_list = json.loads(results['output'])
    my_entry = None
    for entry in pdb_list:
        if entry['Unix username'] == "testuser3":
            my_entry = entry
            break

    assert my_entry is not None, results['output']
    if my_entry is not None:
        assert my_entry["Account Flags"] == "[U          ]", str(my_entry)


def test_53_deleting_non_smb_user(request):
    depends(request, ["NON_SMB_USER_CREATED"])
    results = DELETE(f"/user/id/{user_id}/", {"delete_group": True})
    assert results.status_code == 200, results.text


def test_54_destroying_home_dataset(request):
    depends(request, ["HOME_DS_CREATED"])
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text


def test_55_check_no_builtin_smb_users(request):
    """
    We have builtin SMB groups, but should have no builtin
    users. Failure here may indicate an issue with builtin user
    synchronization code in middleware. Failure to catch this
    may lead to accidentally granting SMB access to builtin
    accounts.
    """
    result = GET(
        '/user', payload={
            'query-filters': [['builtin', '=', True], ['smb', '=', True]],
            'query-options': {'count': True},
        }
    )
    assert result.json() == 0, result.text
