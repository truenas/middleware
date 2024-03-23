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
from auto_config import user, password, ip
from middlewared.test.integration.utils import call
from pytest_dependency import depends
GroupIdFile = "/tmp/.ixbuild_test_groupid"
pytestmark = pytest.mark.accounts


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
    assert result.json()['sid'] == "", result.text
    assert result.json()['nt_name'] == "", result.text


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
    result = GET(
        '/group', payload={
            'query-filters': [['name', '=', 'newgroup']],
            'query-options': {
                'get': True,
                'extra': {'additional_information': ['SMB']}
            }
        }
    )
    assert result.status_code == 200, result.text
    assert result.json()['sid'], result.text
    assert result.json()['nt_name'], result.text


# Delete the group
def test_19_delete_group_testgroup_newgroup():
    results = DELETE(f"/group/id/{groupid}/", {"delete_users": True})
    assert results.status_code == 200, results.text


def test_20_look_group_is_delete():
    assert len(GET('/group?group=newuser').json()) == 0


def test_21_look_for_newgroup_is_not_in_freenas_group(request):
    payload = {
        "groupname": "newgroup"
    }
    results = POST("/group/get_group_obj/", payload)
    assert results.status_code == 500, results.text


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
    global old_groupmap_sid
    global gid_to_check
    result = GET(
        '/group', payload={
            'query-filters': [['name', '=', 'smbgroup']],
            'query-options': {
                'get': True,
                'extra': {'additional_information': ['SMB']}
            }
        }
    )
    assert result.status_code == 200, result.text
    assert result.json()['sid'], result.text
    assert result.json()['nt_name'], result.text
    old_groupmap_sid = result.json()['sid']
    gid_to_check = result.json()['gid']


def test_25_test_name_change_smb_group(request):
    depends(request, ["SMB_GROUP_CREATED"])
    payload = {
        "name": "newsmbgroup"
    }
    results = PUT("/group/id/%s" % groupid, payload)
    assert results.status_code == 200, results.text


def test_26_groupmap_entry_nt_name_change(request):
    """
    Changing the name of an SMB group should not result in
    a SID change.
    """
    depends(request, ["SMB_GROUP_CREATED"], scope="session")
    result = GET(
        '/group', payload={
            'query-filters': [['name', '=', 'newsmbgroup']],
            'query-options': {
                'get': True,
                'extra': {'additional_information': ['SMB']}
            }
        }
    )
    assert result.status_code == 200, result.text
    assert result.json()['nt_name'] == 'newsmbgroup', result.text
    assert result.json()['sid'] == old_groupmap_sid, result.text


def test_27_full_groupmap_check(request):
    """
    Full check of groupmap contents
    """
    depends(request, ["SMB_GROUP_CREATED"], scope="session")
    cmd = "midclt call smb.groupmap_list"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'], str(results['output'])

    gm = json.loads(results['stdout'].strip())
    assert gm['localsid'], str(gm)

    for k, entry in gm['local_builtins'].items():
        assert entry['sid'].startswith(gm['localsid']), str(entry)
        assert int(k) == entry['gid'], str(entry)
        nt_name_suffix = entry['nt_name'].split('_')[1]
        unix_name_suffix = entry['unix_group'].split('_')[1]
        assert nt_name_suffix == unix_name_suffix, str(entry)

    for k in ['544', '546']:
        assert k in gm['local_builtins'], str(gm['local_builtins'])

    for i in [
        ('90000001', 'S-1-5-32-544'),
        ('90000002', 'S-1-5-32-545'),
        ('90000003', 'S-1-5-32-546'),
    ]:
        gid, sid = i
        entry = gm['builtins'][gid]
        assert entry['sid'] == sid, str(entry)
        assert entry['unix_group'] == f'BUILTIN\\{entry["nt_name"].lower()}', str(entry)
        assert entry['group_type_int'] == 4, str(entry)
        assert int(gid) == entry['gid'], str(entry)

    assert str(gid_to_check) in gm['local'], str(gm)

    cmd = "midclt call smb.groupmap_listmem S-1-5-32-544"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'], str(results['output'])
    ba = json.loads(results['stdout'].strip())
    assert gm['local_builtins']['544']['sid'] in ba, str(ba)

    cmd = "midclt call smb.groupmap_listmem S-1-5-32-546"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'], str(results['output'])
    bg = json.loads(results['stdout'].strip())
    assert gm['local_builtins']['546']['sid'] in bg, str(bg)


def test_28_convert_smb_group_to_non_smb(request):
    depends(request, ["SMB_GROUP_CREATED"])
    payload = {
        "smb": False
    }
    results = PUT("/group/id/%s" % groupid, payload)
    assert results.status_code == 200, results.text
    result = GET(
        '/group', payload={
            'query-filters': [['name', '=', 'newsmbgroup']],
            'query-options': {
                'get': True,
                'extra': {'additional_information': ['SMB']}
            }
        }
    )
    assert result.status_code == 200, result.text
    assert result.json()['sid'] == "", result.text
    assert result.json()['nt_name'] == "", result.text


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
