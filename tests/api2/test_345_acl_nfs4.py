#!/usr/bin/env python3

# License: BSD

import sys
import os
import pytest
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, SSH_TEST, wait_on_job
from auto_config import ip, pool_name, user, password
from pytest_dependency import depends

ACLTEST_DATASET = f'{pool_name}/acltest'
dataset_url = ACLTEST_DATASET.replace('/', '%2F')

ACLTEST_SUBDATASET = f'{pool_name}/acltest/sub1'
subdataset_url = ACLTEST_SUBDATASET.replace('/', '%2F')

base_permset = {
    "READ_DATA": False,
    "WRITE_DATA": False,
    "APPEND_DATA": False,
    "READ_NAMED_ATTRS": False,
    "WRITE_NAMED_ATTRS": False,
    "EXECUTE": False,
    "DELETE_CHILD": False,
    "READ_ATTRIBUTES": False,
    "WRITE_ATTRIBUTES": False,
    "DELETE": False,
    "READ_ACL": False,
    "WRITE_ACL": False,
    "WRITE_OWNER": False,
    "SYNCHRONIZE": True
}

base_flagset = {
    "FILE_INHERIT": False,
    "DIRECTORY_INHERIT": False,
    "NO_PROPAGATE_INHERIT": False,
    "INHERIT_ONLY": False,
    "INHERITED": False
}

BASIC_PERMS = ["READ", "TRAVERSE", "MODIFY", "FULL_CONTROL"]
BASIC_FLAGS = ["INHERIT", "NOINHERIT"]
TEST_FLAGS = [
     'DIRECTORY_INHERIT',
     'FILE_INHERIT',
     'INHERIT_ONLY',
     'NO_PROPAGATE_INHERIT'
]

INHERIT_FLAGS_BASIC = {
    "FILE_INHERIT": True,
    "DIRECTORY_INHERIT": True,
    "NO_PROPAGATE_INHERIT": False,
    "INHERIT_ONLY": False,
    "INHERITED": False
}

INHERIT_FLAGS_ADVANCED = {
    "FILE_INHERIT": True,
    "DIRECTORY_INHERIT": True,
    "NO_PROPAGATE_INHERIT": True,
    "INHERIT_ONLY": True,
    "INHERITED": False
}

default_acl = [
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
    }
]

JOB_ID = None


def test_01_check_dataset_endpoint():
    assert isinstance(GET('/pool/dataset/').json(), list)


@pytest.mark.dependency(name="DATASET_CREATED")
def test_02_create_dataset(request):
    depends(request, ["pool_04"], scope="session")
    result = POST(
        '/pool/dataset/', {
            'name': ACLTEST_DATASET
        }
    )
    assert result.status_code == 200, result.text

@pytest.mark.dependency(name="HAS_NFS4_ACLS")
def test_03_get_acltype(request):
    depends(request, ["DATASET_CREATED"])
    global results
    payload = {
        'path': f'/mnt/{ACLTEST_DATASET}',
        'simplified': True
    }
    result = POST('/filesystem/getacl/', payload)
    assert result.status_code == 200, results.text
    if result.json()['acltype'] != "NFS4":
        pytest.skip("Incorrect ACL type")

def test_04_basic_set_acl_for_dataset(request):
    depends(request, ["HAS_NFS4_ACLS"])
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': default_acl,
            'group': 'nobody',
            'user': 'nobody'
        }
    )

    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

def test_05_get_filesystem_getacl(request):
    depends(request, ["HAS_NFS4_ACLS"])
    global results
    payload = {
        'path': f'/mnt/{ACLTEST_DATASET}',
        'simplified': True
    }
    results = POST('/filesystem/getacl/', payload)
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('key', ['tag', 'type', 'perms', 'flags'])
def test_06_verify_filesystem_getacl(request, key):
    depends(request, ["HAS_NFS4_ACLS"])
    assert results.json()['acl'][0][key] == default_acl[0][key], results.text
    assert results.json()['acl'][1][key] == default_acl[1][key], results.text


def test_07_verify_setacl_chown(request):
    depends(request, ["HAS_NFS4_ACLS"])
    assert results.json()['uid'] == 65534, results.text


"""
At this point very basic functionality of API endpoint is verified.
Proceed to more rigorous testing of basic and advanced permissions.
These tests will only manipulate the first entry in the default ACL (owner@).
Each test will iterate through all available options for that particular
variation (BASIC/ADVANCED permissions, BASIC/ADVANCED flags).
"""


@pytest.mark.parametrize('permset', BASIC_PERMS)
def test_08_set_basic_permsets(request, permset):
    depends(request, ["HAS_NFS4_ACLS"])
    payload = {
        'path': f'/mnt/{ACLTEST_DATASET}',
        'simplified': True
    }
    default_acl[0]['perms']['BASIC'] = permset
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': default_acl,
            'group': 'nobody',
            'user': 'nobody'
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    results = POST('/filesystem/getacl/', payload)
    assert results.status_code == 200, results.text
    requested_perms = default_acl[0]['perms']
    received_perms = results.json()['acl'][0]['perms']
    assert requested_perms == received_perms, results.text


@pytest.mark.parametrize('flagset', BASIC_FLAGS)
def test_09_set_basic_flagsets(request, flagset):
    depends(request, ["HAS_NFS4_ACLS"])
    payload = {
        'path': f'/mnt/{ACLTEST_DATASET}',
        'simplified': True
    }
    default_acl[0]['flags']['BASIC'] = flagset
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': default_acl,
            'group': 'nobody',
            'user': 'nobody'
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    results = POST('/filesystem/getacl/', payload)
    assert results.status_code == 200, results.text
    requested_flags = default_acl[0]['flags']
    received_flags = results.json()['acl'][0]['flags']
    assert received_flags == requested_flags, results.text


@pytest.mark.parametrize('perm', base_permset.keys())
def test_10_set_advanced_permset(request, perm):
    depends(request, ["HAS_NFS4_ACLS"])
    payload = {
        'path': f'/mnt/{ACLTEST_DATASET}',
        'simplified': False
    }
    for key in ['perms', 'flags']:
        if default_acl[0][key].get('BASIC'):
            default_acl[0][key].pop('BASIC')

    default_acl[0]['flags'] = base_flagset.copy()
    default_acl[0]['perms'] = base_permset.copy()
    default_acl[0]['perms'][perm] = True
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': default_acl,
            'group': 'nobody',
            'user': 'nobody'
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    results = POST('/filesystem/getacl/', payload)
    assert results.status_code == 200, results.text
    requested_perms = default_acl[0]['perms']
    received_perms = results.json()['acl'][0]['perms']
    assert requested_perms == received_perms, results.text


@pytest.mark.parametrize('flag', TEST_FLAGS)
def test_11_set_advanced_flagset(request, flag):
    depends(request, ["HAS_NFS4_ACLS"])
    payload = {
        'path': f'/mnt/{ACLTEST_DATASET}',
        'simplified': False
    }
    default_acl[0]['flags'] = base_flagset.copy()
    default_acl[0]['flags'][flag] = True
    if flag in ['INHERIT_ONLY', 'NO_PROPAGATE_INHERIT']:
        default_acl[0]['flags']['DIRECTORY_INHERIT'] = True

    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': default_acl,
            'group': 'nobody',
            'user': 'nobody'
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    results = POST('/filesystem/getacl/', payload)
    assert results.status_code == 200, results.text
    requested_flags = default_acl[0]['flags']
    received_flags = results.json()['acl'][0]['flags']
    assert received_flags == requested_flags, results.text


"""
This next series of tests verifies that ACLs are being inherited correctly.
We first create a child dataset to verify that ACLs do not change unless
'traverse' is set.
"""


def test_12_prepare_recursive_tests(request):
    depends(request, ["HAS_NFS4_ACLS"])
    result = POST(
        '/pool/dataset/', {
            'name': ACLTEST_SUBDATASET
        }
    )
    assert result.status_code == 200, result.text

    cmd = f'mkdir -p /mnt/{ACLTEST_DATASET}/dir1/dir2'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    cmd = f'touch /mnt/{ACLTEST_DATASET}/dir1/testfile'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    cmd = f'touch /mnt/{ACLTEST_DATASET}/dir1/dir2/testfile'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_13_recursive_no_traverse(request):
    depends(request, ["HAS_NFS4_ACLS"])
    default_acl[1]['perms'].pop('BASIC')
    default_acl[1]['flags'].pop('BASIC')
    default_acl[0]['flags'] = INHERIT_FLAGS_BASIC.copy()
    default_acl[1]['flags'] = INHERIT_FLAGS_ADVANCED.copy()

    expected_flags_0 = INHERIT_FLAGS_BASIC.copy()
    expected_flags_0['INHERITED'] = True
    expected_flags_1 = base_flagset.copy()
    expected_flags_1['INHERITED'] = True

    # get acl of child dataset. This should not  change in this test
    results = POST('/filesystem/getacl/',
                   {'path': f'/mnt/{ACLTEST_SUBDATASET}', 'simplified': True})
    assert results.status_code == 200, results.text
    init_acl = results.json()['acl'][0]['perms']

    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': default_acl,
            'group': 'nobody',
            'user': 'nobody',
            'options': {'recursive': True}
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    # Verify that it hasn't changed
    results = POST('/filesystem/getacl/',
                   {'path': f'/mnt/{ACLTEST_SUBDATASET}', 'simplified': True})
    assert results.status_code == 200, results.text
    fin_acl = results.json()['acl'][0]['perms']
    assert init_acl == fin_acl, results.text

    # check on dir 1. Entry 1 should have INHERIT flag added, and
    # INHERIT_ONLY should be set to False at this depth.
    results = POST('/filesystem/getacl/', {
                       'path': f'/mnt/{ACLTEST_DATASET}/dir1',
                       'simplified': False
                   })
    assert results.status_code == 200, results.text
    theacl = results.json()['acl']
    assert theacl[0]['flags'] == expected_flags_0, results.text
    assert theacl[1]['flags'] == expected_flags_1, results.text

    # Verify that user was changed on subdirectory
    assert results.json()['uid'] == 65534, results.text

    # check on dir 2 - the no propogate inherit flag should have taken
    # effect and ACL length should be 1
    results = POST('/filesystem/getacl/', {
                       'path': f'/mnt/{ACLTEST_DATASET}/dir1/dir2',
                       'simplified': False
                   })
    assert results.status_code == 200, results.text
    theacl = results.json()['acl']
    assert theacl[0]['flags'] == expected_flags_0, results.text
    assert len(theacl) == 1, results.text

    # Verify that user was changed two deep
    assert results.json()['uid'] == 65534, results.text


def test_14_recursive_with_traverse(request):
    depends(request, ["HAS_NFS4_ACLS"])
    expected_flags_0 = INHERIT_FLAGS_BASIC.copy()
    expected_flags_0['INHERITED'] = True
    expected_flags_1 = base_flagset.copy()
    expected_flags_1['INHERITED'] = True
    payload = {
        'path': f'/mnt/{ACLTEST_SUBDATASET}',
        'simplified': False
    }
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': default_acl,
            'group': 'nobody',
            'user': 'nobody',
            'options': {'recursive': True, 'traverse': True}
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    results = POST('/filesystem/getacl/', payload)
    assert results.status_code == 200, results.text
    theacl = results.json()['acl']
    assert theacl[0]['flags'] == expected_flags_0, results.text
    assert theacl[1]['flags'] == expected_flags_1, results.text

    # Verify that user was changed
    assert results.json()['uid'] == 65534, results.text


def test_15_strip_acl_from_dataset(request):
    depends(request, ["HAS_NFS4_ACLS"])
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': [],
            'mode': '777',
            'group': 'nobody',
            'user': 'nobody',
            'options': {'stripacl': True, 'recursive': True}
        }
    )

    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


"""
The next four tests check that we've remotved the ACL from the
mountpoint, a subdirectory, and a file. These are all potentially
different cases for where we can fail to strip an ACL.
"""


def test_16_filesystem_acl_is_not_removed_child_dataset(request):
    depends(request, ["HAS_NFS4_ACLS"])
    results = POST('/filesystem/stat/', f'/mnt/{ACLTEST_SUBDATASET}')
    assert results.status_code == 200, results.text
    assert results.json()['acl'] is True, results.text


def test_17_filesystem_acl_is_removed_mountpoint(request):
    depends(request, ["HAS_NFS4_ACLS"])
    results = POST('/filesystem/stat/', f'/mnt/{ACLTEST_DATASET}')
    assert results.status_code == 200, results.text
    assert results.json()['acl'] is False, results.text
    assert oct(results.json()['mode']) == '0o40777', results.text


def test_18_filesystem_acl_is_removed_subdir(request):
    depends(request, ["HAS_NFS4_ACLS"])
    results = POST('/filesystem/stat/', f'/mnt/{ACLTEST_DATASET}/dir1')
    assert results.status_code == 200, results.text
    assert results.json()['acl'] is False, results.text
    assert oct(results.json()['mode']) == '0o40777', results.text


def test_19_filesystem_acl_is_removed_file(request):
    depends(request, ["HAS_NFS4_ACLS"])
    results = POST('/filesystem/stat/',
                   f'/mnt/{ACLTEST_DATASET}/dir1/testfile')
    assert results.status_code == 200, results.text
    assert results.json()['acl'] is False, results.text
    assert oct(results.json()['mode']) == '0o100777', results.text


def test_20_delete_child_dataset(request):
    depends(request, ["HAS_NFS4_ACLS"])
    result = DELETE(
        f'/pool/dataset/id/{subdataset_url}/'
    )
    assert result.status_code == 200, result.text


def test_21_delete_dataset(request):
    depends(request, ["pool_04"], scope="session")
    result = DELETE(
        f'/pool/dataset/id/{dataset_url}/'
    )
    assert result.status_code == 200, result.text
