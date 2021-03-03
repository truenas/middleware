#!/usr/bin/env python3

# License: BSD

import sys
import os
import pytest
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, SSH_TEST, wait_on_job
from auto_config import ip, pool_name, user, password, scale
from pytest_dependency import depends

from auto_config import dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

shell = '/usr/bin/bash' if scale else '/bin/csh'
group = 'nogroup' if scale else 'nobody'
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

function_testing_acl_deny = [
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
        "perms": {"BASIC": "FULL_CONTROL"},
        "flags": {"BASIC": "INHERIT"}
    },
]

function_testing_acl_allow = [
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

ACL_USER = "acluser"
ACL_PWD = "acl1234"

# base64-encoded samba DOSATTRIB xattr
DOSATTRIB_XATTR = "CTB4MTAAAAMAAwAAABEAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABimX3sSqfTAQAAAAAAAAAACg=="

IMPLEMENTED_DENY = [
    "READ_ATTRIBUTES",
    "WRITE_ATTRIBUTES",
    "DELETE",
    "DELETE_CHILD",
    "FULL_DELETE",
    "EXECUTE",
    "READ_DATA",
    "WRITE_DATA",
    "READ_ACL",
    "WRITE_ACL",
    "WRITE_OWNER",
]

IMPLEMENTED_ALLOW = [
    "READ_DATA",
    "WRITE_DATA",
    "DELETE",
    "DELETE_CHILD",
    "EXECUTE",
    "WRITE_OWNER",
    "READ_ATTRIBUTES",
    "WRITE_ATTRIBUTES",
    "READ_ACL",
    "WRITE_ACL",
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
            'group': group,
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
            'group': group,
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
            'group': group,
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
            'group': group,
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
            'group': group,
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
    depends(request, ["HAS_NFS4_ACLS", "ssh_password"], scope="session")
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
            'group': group,
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
    results = POST(
        '/filesystem/getacl/', {
            'path': f'/mnt/{ACLTEST_DATASET}/dir1',
            'simplified': False
        }
    )
    assert results.status_code == 200, results.text
    theacl = results.json()['acl']
    assert theacl[0]['flags'] == expected_flags_0, results.text
    assert theacl[1]['flags'] == expected_flags_1, results.text

    # Verify that user was changed on subdirectory
    assert results.json()['uid'] == 65534, results.text

    # check on dir 2 - the no propogate inherit flag should have taken
    # effect and ACL length should be 1
    results = POST(
        '/filesystem/getacl/', {
            'path': f'/mnt/{ACLTEST_DATASET}/dir1/dir2',
            'simplified': False
        }
    )
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
            'group': group,
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
            'group': group,
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


def test_20_get_next_uid_for_acluser():
    results = GET('/user/get_next_uid/')
    assert results.status_code == 200, results.text
    global next_uid
    next_uid = results.json()


@pytest.mark.dependency(name="ACL_USER_CREATED")
def test_21_creating_shareuser_to_test_acls():
    global acluser_id
    payload = {
        "username": ACL_USER,
        "full_name": "ACL User",
        "group_create": True,
        "password": ACL_PWD,
        "uid": next_uid,
        "shell": shell}
    results = POST("/user/", payload)
    assert results.status_code == 200, results.text
    acluser_id = results.json()


@pytest.mark.dependency(name="HAS_TESTFILE")
def test_22_prep_testfile(request):
    depends(request, ["ACL_USER_CREATED", "ssh_password"], scope="session")
    cmd = f'touch /mnt/{ACLTEST_DATASET}/acltest.txt'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    cmd = f'echo -n "CAT" >> /mnt/{ACLTEST_DATASET}/acltest.txt'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


"""
The following tests verify that DENY ACEs are functioning correctly.
Deny ace will be prepended to base ACL that grants FULL_CONTROL.

#define VREAD_NAMED_ATTRS       000000200000 /* not used */
#define VWRITE_NAMED_ATTRS      000000400000 /* not used */
#define VDELETE_CHILD           000001000000
#define VREAD_ATTRIBUTES        000002000000 /* permission to stat(2) */
#define VWRITE_ATTRIBUTES       000004000000 /* change {m,c,a}time */
#define VDELETE                 000010000000
#define VREAD_ACL               000020000000 /* read ACL and file mode */
#define VWRITE_ACL              000040000000 /* change ACL and/or file mode */
#define VWRITE_OWNER            000100000000 /* change file owner */
#define VSYNCHRONIZE            000200000000 /* not used */

Some tests must be skipped due to lack of implementation in VFS.
"""


@pytest.mark.parametrize('perm', IMPLEMENTED_DENY)
def test_23_test_acl_function_deny(perm, request):
    """
    Iterate through available permissions and prepend
    deny ACE denying that particular permission to the
    acltest user, then attempt to perform an action that
    should result in failure.
    """
    depends(request, ["ACL_USER_CREATED", "HAS_TESTFILE", "ssh_password", "acl_pool_perm_09"], scope="session")

    if perm == "FULL_DELETE":
        to_deny = {"DELETE_CHILD": True, "DELETE": True}
    else:
        to_deny = {perm: True}

    payload_acl = [{
        "tag": "USER",
        "id": next_uid,
        "type": "DENY",
        "perms": to_deny,
        "flags": {"BASIC": "INHERIT"}
    }]
    payload_acl.extend(function_testing_acl_deny)
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': payload_acl,
            'group': 'wheel',
            'user': 'root',
            'options': {'recursive': True},
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    if job_status['state'] != 'SUCCESS':
        return

    if perm == "EXECUTE":
        cmd = f'cd /mnt/{ACLTEST_DATASET}'

    elif perm == "READ_ATTRIBUTES":
        cmd = f'stat /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm in ["DELETE", "DELETE_CHILD", "FULL_DELETE"]:
        cmd = f'rm /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "READ_DATA":
        cmd = f'cat /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_DATA":
        cmd = f'echo -n "CAT" >> /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_ATTRIBUTES":
        cmd = f'touch -a -m -t 201512180130.09 /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "READ_ACL":
        cmd = f'getfacl /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_ACL":
        cmd = f'setfacl -b /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_OWNER":
        cmd = f'chown {ACL_USER} /mnt/{ACLTEST_DATASET}/acltest.txt'

    else:
        # This should never happen.
        cmd = "touch /var/empty/ERROR"

    results = SSH_TEST(cmd, ACL_USER, ACL_PWD, ip)
    """
    Per RFC5661 Section 6.2.1.3.2, deletion is permitted if either
    DELETE_CHILD is permitted on parent, or DELETE is permitted on
    file. This means that it should succeed when tested in isolation,
    but fail when combined.
    """
    errstr = f'cmd: {cmd}, res: {results["output"]}, to_deny {to_deny}'
    if perm in ["DELETE", "DELETE_CHILD"]:
        assert results['result'] is True, errstr

        # unfortunately, we now need to recreate our testfile.
        cmd = f'touch /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, user, password, ip)
        assert results['result'] is True, results['output']

        cmd = f'echo -n "CAT" >> /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, user, password, ip)
        assert results['result'] is True, results['output']

    else:
        assert results['result'] is False, errstr


@pytest.mark.parametrize('perm', IMPLEMENTED_ALLOW)
def test_24_test_acl_function_allow(perm, request):
    """
    Iterate through available permissions and prepend
    allow ACE permitting that particular permission to the
    acltest user, then attempt to perform an action that
    should result in success.
    """
    depends(request, ["ACL_USER_CREATED", "HAS_TESTFILE", "ssh_password", "acl_pool_perm_09"], scope="session")

    """
    Some extra permissions bits must be set for these tests
    EXECUTE so that we can traverse to the path in question
    and READ_ATTRIBUTES because most of the utilites we use
    for testing have to stat(2) the files.
    """
    to_allow = {perm: True}
    if perm != "EXECUTE":
        to_allow["EXECUTE"] = True

    if perm != "READ_ATTRIBUTES":
        to_allow["READ_ATTRIBUTES"] = True

    if perm == "WRITE_ACL":
        to_allow["READ_ACL"] = True

    payload_acl = [{
        "tag": "USER",
        "id": next_uid,
        "type": "ALLOW",
        "perms": to_allow,
        "flags": {"BASIC": "INHERIT"}
    }]
    payload_acl.extend(function_testing_acl_allow)
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': payload_acl,
            'group': group,
            'user': 'root',
            'options': {'recursive': True},
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    if job_status['state'] != 'SUCCESS':
        return

    if perm == "EXECUTE":
        cmd = f'cd /mnt/{ACLTEST_DATASET}'

    elif perm == "READ_ATTRIBUTES":
        cmd = f'stat /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm in ["DELETE", "DELETE_CHILD", "FULL_DELETE"]:
        cmd = f'rm /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "READ_DATA":
        cmd = f'cat /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_DATA":
        cmd = f'echo -n "CAT" >> /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_ATTRIBUTES":
        cmd = f'touch -a -m -t 201512180130.09 /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "READ_ACL":
        cmd = f'getfacl /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_ACL":
        cmd = f'setfacl -x 0 /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_OWNER":
        cmd = f'chown {ACL_USER} /mnt/{ACLTEST_DATASET}/acltest.txt'

    else:
        # This should never happen.
        cmd = "touch /var/empty/ERROR"

    results = SSH_TEST(cmd, ACL_USER, ACL_PWD, ip)
    errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
    assert results['result'] is True, errstr
    if perm in ["DELETE", "DELETE_CHILD"]:
        # unfortunately, we now need to recreate our testfile.
        cmd = f'touch /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, user, password, ip)
        assert results['result'] is True, results['output']

        cmd = f'echo -n "CAT" >> /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, user, password, ip)
        assert results['result'] is True, results['output']


@pytest.mark.parametrize('perm', IMPLEMENTED_ALLOW)
def test_25_test_acl_function_omit(perm, request):
    """
    Iterate through available permissions and add permissions
    required for an explicit ALLOW of that ACE from the previous
    test to succeed. This sets the stage to have success hinge
    on presence of the particular permissions bit. Then we omit
    it. This should result in a failure.
    """
    depends(request, ["ACL_USER_CREATED", "HAS_TESTFILE", "acl_pool_perm_09"], scope="session")

    """
    Some extra permissions bits must be set for these tests
    EXECUTE so that we can traverse to the path in question
    and READ_ATTRIBUTES because most of the utilites we use
    for testing have to stat(2) the files.
    """
    to_allow = {}
    if perm != "EXECUTE":
        to_allow["EXECUTE"] = True

    if perm != "READ_ATTRIBUTES":
        to_allow["READ_ATTRIBUTES"] = True

    if perm == "WRITE_ACL":
        to_allow["READ_ACL"] = True

    payload_acl = [{
        "tag": "USER",
        "id": next_uid,
        "type": "ALLOW",
        "perms": to_allow,
        "flags": {"BASIC": "INHERIT"}
    }]

    payload_acl.extend(function_testing_acl_allow)
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': payload_acl,
            'group': group,
            'user': 'root',
            'options': {'recursive': True},
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    if job_status['state'] != 'SUCCESS':
        return

    if perm == "EXECUTE":
        cmd = f'cd /mnt/{ACLTEST_DATASET}'

    elif perm == "READ_ATTRIBUTES":
        cmd = f'stat /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm in ["DELETE", "DELETE_CHILD", "FULL_DELETE"]:
        cmd = f'rm /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "READ_DATA":
        cmd = f'cat /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_DATA":
        cmd = f'echo -n "CAT" >> /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_ATTRIBUTES":
        cmd = f'touch -a -m -t 201512180130.09 /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "READ_ACL":
        cmd = f'getfacl /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_ACL":
        cmd = f'setfacl -x 0 /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_OWNER":
        cmd = f'chown {ACL_USER} /mnt/{ACLTEST_DATASET}/acltest.txt'

    else:
        # This should never happen.
        cmd = "touch /var/empty/ERROR"

    results = SSH_TEST(cmd, ACL_USER, ACL_PWD, ip)
    errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
    assert results['result'] is False, errstr


@pytest.mark.parametrize('perm', IMPLEMENTED_ALLOW)
def test_25_test_acl_function_allow_restrict(perm, request):
    """
    Iterate through implemented allow permissions and verify that
    they grant no more permissions than intended. Some bits cannot
    be tested in isolation effectively using built in utilities.
    """
    depends(request, ["ACL_USER_CREATED", "HAS_TESTFILE", "ssh_password", "acl_pool_perm_09"], scope="session")

    """
    Some extra permissions bits must be set for these tests
    EXECUTE so that we can traverse to the path in question
    and READ_ATTRIBUTES because most of the utilites we use
    for testing have to stat(2) the files.
    """
    to_allow = {}
    tests_to_skip = []
    tests_to_skip.append(perm)

    if perm != "EXECUTE":
        to_allow["EXECUTE"] = True
        tests_to_skip.append("EXECUTE")

    if perm != "READ_ATTRIBUTES":
        to_allow["READ_ATTRIBUTES"] = True
        tests_to_skip.append("READ_ATTRIBUTES")

    if perm == "DELETE_CHILD":
        tests_to_skip.append("DELETE")

    payload_acl = [{
        "tag": "USER",
        "id": next_uid,
        "type": "ALLOW",
        "perms": to_allow,
        "flags": {"BASIC": "INHERIT"}
    }]
    payload_acl.extend(function_testing_acl_allow)
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': payload_acl,
            'group': group,
            'user': 'root',
            'options': {'recursive': True},
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    if job_status['state'] != 'SUCCESS':
        return

    if "EXECUTE" not in tests_to_skip:
        cmd = f'cd /mnt/{ACLTEST_DATASET}'
        results = SSH_TEST(cmd, ACL_USER, ACL_PWD, ip)
        errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
        assert results['result'] is False, errstr

    if "DELETE" not in tests_to_skip:
        cmd = f'rm /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, ACL_USER, ACL_PWD, ip)
        errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
        assert results['result'] is False, errstr
        if results['result'] is True:
            # File must be re-created. Kernel ACL inheritance routine
            # will ensure that new file has right ACL.
            cmd = f'touch /mnt/{ACLTEST_DATASET}/acltest.txt'
            results = SSH_TEST(cmd, user, password, ip)
            assert results['result'] is True, results['output']

            cmd = f'echo -n "CAT" >> /mnt/{ACLTEST_DATASET}/acltest.txt'
            results = SSH_TEST(cmd, user, password, ip)
            assert results['result'] is True, results['output']

    if "READ_DATA" not in tests_to_skip:
        cmd = f'cat /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, ACL_USER, ACL_PWD, ip)
        errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
        assert results['result'] is False, errstr

    if "WRITE_DATA" not in tests_to_skip:
        cmd = f'echo -n "CAT" >> /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, ACL_USER, ACL_PWD, ip)
        errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
        assert results['result'] is False, errstr

    if "WRITE_ATTRIBUTES" not in tests_to_skip:
        cmd = f'touch -a -m -t 201512180130.09 /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, ACL_USER, ACL_PWD, ip)
        errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
        assert results['result'] is False, errstr

    if "READ_ACL" not in tests_to_skip:
        cmd = f'getfacl /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, ACL_USER, ACL_PWD, ip)
        errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
        assert results['result'] is False, errstr

    if "WRITE_ACL" not in tests_to_skip:
        cmd = f'setfacl -x 0 /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, ACL_USER, ACL_PWD, ip)
        errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
        assert results['result'] is False, errstr

    if "WRITE_OWNER" not in tests_to_skip:
        cmd = f'chown {ACL_USER} /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, ACL_USER, ACL_PWD, ip)
        errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
        assert results['result'] is False, errstr


def test_26_file_execute_deny(request):
    """
    Base permset with everyone@ FULL_CONTROL, but ace added on
    top explictly denying EXECUTE. Attempt to execute file should fail.
    """
    depends(request, ["ACL_USER_CREATED", "HAS_TESTFILE", "ssh_password", "acl_pool_perm_09"], scope="session")
    payload_acl = [
        {
            "tag": "USER",
            "id": next_uid,
            "type": "DENY",
            "perms": {"EXECUTE": True},
            "flags": {"FILE_INHERIT": True}
        },
        {
            "tag": "USER",
            "id": next_uid,
            "type": "ALLOW",
            "perms": {"EXECUTE": True},
            "flags": {"BASIC": "NOINHERIT"}
        },
    ]
    payload_acl.extend(function_testing_acl_deny)
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': payload_acl,
            'group': 'wheel',
            'user': 'root',
            'options': {'recursive': True},
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    if job_status['state'] != 'SUCCESS':
        return

    cmd = f'echo "echo CANARY" > /mnt/{ACLTEST_DATASET}/acltest.txt'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    cmd = f'/mnt/{ACLTEST_DATASET}/acltest.txt'
    results = SSH_TEST(cmd, ACL_USER, ACL_PWD, ip)
    errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {payload_acl}'
    assert results['result'] is False, errstr


def test_27_file_execute_allow(request):
    """
    Verify that setting execute allows file execution. READ_DATA and
    READ_ATTRIBUTES are also granted beecause we need to be able to
    stat and read our test script.
    """
    depends(request, ["ACL_USER_CREATED", "HAS_TESTFILE", "ssh_password", "acl_pool_perm_09"], scope="session")
    payload_acl = [
        {
            "tag": "USER",
            "id": next_uid,
            "type": "ALLOW",
            "perms": {
                "EXECUTE": True,
                "READ_DATA": True,
                "READ_ATTRIBUTES": True
            },
            "flags": {"FILE_INHERIT": True}
        },
        {
            "tag": "USER",
            "id": next_uid,
            "type": "ALLOW",
            "perms": {"EXECUTE": True},
            "flags": {"BASIC": "NOINHERIT"}
        },
    ]
    payload_acl.extend(function_testing_acl_allow)
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': payload_acl,
            'group': 'wheel',
            'user': 'root',
            'options': {'recursive': True},
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    if job_status['state'] != 'SUCCESS':
        return

    cmd = f'echo "echo CANARY" > /mnt/{ACLTEST_DATASET}/acltest.txt'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    cmd = f'/mnt/{ACLTEST_DATASET}/acltest.txt'
    results = SSH_TEST(cmd, ACL_USER, ACL_PWD, ip)
    errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {payload_acl}'
    assert results['result'] is True, errstr


def test_28_file_execute_omit(request):
    """
    Grant user all permissions except EXECUTE. Attempt to execute
    file should fail.
    """
    depends(request, ["ACL_USER_CREATED", "HAS_TESTFILE", "ssh_password", "acl_pool_perm_09"], scope="session")
    payload_acl = [
        {
            "tag": "USER",
            "id": next_uid,
            "type": "ALLOW",
            "perms": base_permset.copy(),
            "flags": {"FILE_INHERIT": True}
        },
        {
            "tag": "USER",
            "id": next_uid,
            "type": "ALLOW",
            "perms": {"EXECUTE": True},
            "flags": {"BASIC": "NOINHERIT"}
        },
    ]
    payload_acl.extend(function_testing_acl_allow)
    # at this point the user's ACE has all perms set
    # remove execute.
    payload_acl[0]['perms']['EXECUTE'] = False
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': payload_acl,
            'group': 'wheel',
            'user': 'root',
            'options': {'recursive': True},
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    if job_status['state'] != 'SUCCESS':
        return

    cmd = f'echo "echo CANARY" > /mnt/{ACLTEST_DATASET}/acltest.txt'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    cmd = f'/mnt/{ACLTEST_DATASET}/acltest.txt'
    results = SSH_TEST(cmd, ACL_USER, ACL_PWD, ip)
    errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {payload_acl}'
    assert results['result'] is False, errstr


def test_29_deleting_homedir_user(request):
    depends(request, ["ACL_USER_CREATED"])
    results = DELETE(f"/user/id/{acluser_id}/", {"delete_group": True})
    assert results.status_code == 200, results.text


def test_30_delete_dataset(request):
    depends(request, ["pool_04"], scope="session")
    result = DELETE(
        f'/pool/dataset/id/{dataset_url}/'
    )
    assert result.status_code == 200, result.text
