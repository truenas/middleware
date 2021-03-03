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
from auto_config import user, password, ip, dev_test
from pytest_dependency import depends
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')
GroupIdFile = "/tmp/.ixbuild_test_groupid"


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
    depends(request, ["ssh_password"], scope="session")
    cmd = 'getent group | grep -q testgroup'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


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
    depends(request, ["ssh_password"], scope="session")
    cmd = 'getent group | grep -q testgroup'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, results['output']


def test_16_look_for_newgroup_is_in_freenas_group(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = 'getent group | grep -q newgroup'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_17_convert_to_smb_group():
    payload = {
        "smb": True,
    }
    results = PUT("/group/id/%s" % groupid, payload)
    assert results.status_code == 200, results.text


def test_18_check_groupmap_added(request):
    """
    Changing "smb" from False to True should result in
    insertion into group_mapping.tdb.
    """
    depends(request, ["ssh_password"], scope="session")
    cmd = 'midclt call smb.groupmap_list'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    if results['result'] is True:
        groupmap = (json.loads(results['output'])).get('newgroup')
        assert groupmap is not None, results['output']


# Delete the group
def test_19_delete_group_testgroup_newgroup():
    results = DELETE(f"/group/id/{groupid}/", {"delete_users": True})
    assert results.status_code == 200, results.text


def test_20_look_group_is_delete():
    assert len(GET('/group?group=newuser').json()) == 0


def test_21_look_for_newgroup_is_not_in_freenas_group(request):
    depends(request, ["ssh_password"], scope="session")
    cmd = 'getent group | grep -q newgroup'
    results = SSH_TEST(cmd, 'root', 'testing', ip)
    assert results['result'] is False, results['output']


# Test new SMB groupmap
def test_22_get_next_gid():
    results = GET('/group/get_next_gid/')
    assert results.status_code == 200, results.text
    global next_gid
    next_gid = results.json()


# Create tests
@pytest.mark.dependency(name="SMB_GROUP_CREATED")
def test_23_creating_smb_group():
    global groupid
    payload = {
        "gid": next_gid,
        "name": "smbgroup",
        "smb": True,
    }
    results = POST("/group/", payload)
    assert results.status_code == 200, results.text
    groupid = results.json()


def test_24_check_groupmap_added(request):
    """
    Creating new group with "smb" = True should result in insertion into
    group_mapping.tdb.
    """
    depends(request, ["SMB_GROUP_CREATED", "ssh_password"], scope="session")
    cmd = 'midclt call smb.groupmap_list'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    global groupmap
    if results['result'] is True:
        groupmap = (json.loads(results['output'])).get('smbgroup')
        assert groupmap is not None, results['output']


def test_25_test_name_change_smb_group(request):
    depends(request, ["SMB_GROUP_CREATED"])
    payload = {
        "name": "newsmbgroup"
    }
    results = PUT("/group/id/%s" % groupid, payload)
    assert results.status_code == 200, results.text


def test_26_old_groupmap_removed_after_name_change(request):
    """
    "net groupmap list" does not show group mappings for unix groups that no
    longer exist. For this reason, we must use tdbdump to verify that the old
    SID entry has been properly removed. Stale groupmap entries may cause
    difficult-to-diagnose group mapping issues.
    """
    depends(request, ["SMB_GROUP_CREATED", "ssh_password"], scope="session")
    cmd = 'tdbdump /var/db/system/samba4/group_mapping.tdb'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    if results['result'] is True:
        for entry in results['output'].splitlines():
            assert groupmap['SID'] not in entry, entry


def test_27_new_groupmap_added_after_name_change(request):
    """
    Verify that new groupmap entry was inserted with correct
    group name.
    """
    depends(request, ["SMB_GROUP_CREATED", "ssh_password"], scope="session")
    cmd = 'midclt call smb.groupmap_list'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    if results['result'] is True:
        groupmap = (json.loads(results['output'])).get('newsmbgroup')
        assert groupmap is not None, results['output']


def test_28_convert_smb_group_to_non_smb(request):
    depends(request, ["SMB_GROUP_CREATED"])
    payload = {
        "smb": False
    }
    results = PUT("/group/id/%s" % groupid, payload)
    assert results.status_code == 200, results.text


def test_29_groupmap_deleted_after_smb_change(request):
    """
    Verify that new groupmap entry was deleted after change to "smb" = False.
    """
    depends(request, ["SMB_GROUP_CREATED", "ssh_password"], scope="session")
    cmd = 'midclt call smb.groupmap_list'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    if results['result'] is True:
        groupmap = (json.loads(results['output'])).get('newsmbgroup')
        assert groupmap is None, results['output']


def test_30_delete_group_smb_newgroup(request):
    depends(request, ["SMB_GROUP_CREATED"])
    results = DELETE(f"/group/id/{groupid}/", {"delete_users": True})
    assert results.status_code == 200, results.text


def test_31_verify_group_deleted(request):
    depends(request, ["SMB_GROUP_CREATED"])
    payload = {
        "groupname": "newsmbgroup"
    }
    results = POST("/group/get_group_obj/", payload)
    assert results.status_code == 500, results.text
