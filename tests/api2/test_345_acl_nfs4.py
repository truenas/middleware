#!/usr/bin/env python3

# License: BSD

import secrets
import string
import sys
import os
import pytest
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, SSH_TEST, wait_on_job
from auto_config import ip, pool_name, user, password
from pytest_dependency import depends
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import user as create_user
from middlewared.test.integration.assets.pool import dataset as make_dataset
from middlewared.test.integration.utils import call, ssh


shell = '/usr/bin/bash'
group = 'nogroup'
ACLTEST_DATASET_NAME = 'acltest'
ACLTEST_DATASET = f'{pool_name}/{ACLTEST_DATASET_NAME}'
dataset_url = ACLTEST_DATASET.replace('/', '%2F')

ACLTEST_SUBDATASET = f'{pool_name}/acltest/sub1'
subdataset_url = ACLTEST_SUBDATASET.replace('/', '%2F')
getfaclcmd = "nfs4xdr_getfacl"
setfaclcmd = "nfs4xdr_setfacl"
group0 = "root"

ACL_USER = 'acluser'
ACL_PWD = ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(10))

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

# base64-encoded samba DOSATTRIB xattr
DOSATTRIB_XATTR = "CTB4MTAAAAMAAwAAABEAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABimX3sSqfTAQAAAAAAAAAACg=="

IMPLEMENTED_DENY = [
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
    "READ_ACL",
    "WRITE_ACL",
]

TEST_INFO = {}


@pytest.fixture(scope='module')
def initialize_for_acl_tests(request):
    with make_dataset(ACLTEST_DATASET_NAME, data={'acltype': 'NFSV4', 'aclmode': 'RESTRICTED'}) as ds:
        with create_user({
            'username': ACL_USER,
            'full_name': ACL_USER,
            'group_create': True,
            'ssh_password_enabled': True,
            'password': ACL_PWD
        }) as u:
            TEST_INFO.update({
                'dataset': ds,
                'dataset_path': os.path.join('/mnt', ds),
                'user': u
            })
            yield request


@pytest.mark.dependency(name='HAS_NFS4_ACLS')
def test_02_create_dataset(initialize_for_acl_tests):
    acl = call('filesystem.getacl', TEST_INFO['dataset_path'])
    assert acl['acltype'] == 'NFS4'


def test_04_basic_set_acl_for_dataset(request):
    depends(request, ["HAS_NFS4_ACLS"])
    call('pool.dataset.permission', TEST_INFO['dataset'], {
        'acl': default_acl,
        'group': group,
        'user': 'nobody'
    }, job=True)

    acl_result = call('filesystem.getacl', TEST_INFO['dataset_path'],  True)
    for key in ['tag', 'type', 'perms', 'flags']:
        assert acl_result['acl'][0][key] == default_acl[0][key], str(acl_result)
        assert acl_result['acl'][1][key] == default_acl[1][key], str(acl_result)

    assert acl_result['uid'] == 65534, str(acl_result)


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
    default_acl[0]['perms']['BASIC'] = permset

    call('filesystem.setacl', {'path': TEST_INFO['dataset_path'], 'dacl': default_acl}, job=True)
    acl_result = call('filesystem.getacl', TEST_INFO['dataset_path'], True)
    requested_perms = default_acl[0]['perms']
    received_perms = acl_result['acl'][0]['perms']
    assert requested_perms == received_perms, str(acl_result)


@pytest.mark.parametrize('flagset', BASIC_FLAGS)
def test_09_set_basic_flagsets(request, flagset):
    depends(request, ["HAS_NFS4_ACLS"])
    default_acl[0]['flags']['BASIC'] = flagset

    call('filesystem.setacl', {'path': TEST_INFO['dataset_path'], 'dacl': default_acl}, job=True)
    acl_result = call('filesystem.getacl', TEST_INFO['dataset_path'], True)
    requested_flags = default_acl[0]['flags']
    received_flags = acl_result['acl'][0]['flags']
    assert requested_flags == received_flags, str(acl_result)


@pytest.mark.parametrize('perm', base_permset.keys())
def test_10_set_advanced_permset(request, perm):
    depends(request, ["HAS_NFS4_ACLS"])
    for key in ['perms', 'flags']:
        if default_acl[0][key].get('BASIC'):
            default_acl[0][key].pop('BASIC')

    default_acl[0]['flags'] = base_flagset.copy()
    default_acl[0]['perms'] = base_permset.copy()
    default_acl[0]['perms'][perm] = True

    call('filesystem.setacl', {'path': TEST_INFO['dataset_path'], 'dacl': default_acl}, job=True)
    acl_result = call('filesystem.getacl', TEST_INFO['dataset_path'], True)
    requested_perms = default_acl[0]['perms']
    received_perms = acl_result['acl'][0]['perms']
    assert requested_perms == received_perms, str(acl_result)


@pytest.mark.parametrize('flag', TEST_FLAGS)
def test_11_set_advanced_flagset(request, flag):
    depends(request, ["HAS_NFS4_ACLS"])
    default_acl[0]['flags'] = base_flagset.copy()
    default_acl[0]['flags'][flag] = True
    if flag in ['INHERIT_ONLY', 'NO_PROPAGATE_INHERIT']:
        default_acl[0]['flags']['DIRECTORY_INHERIT'] = True

    call('filesystem.setacl', {'path': TEST_INFO['dataset_path'], 'dacl': default_acl}, job=True)
    acl_result = call('filesystem.getacl', TEST_INFO['dataset_path'], True)
    requested_flags = default_acl[0]['flags']
    received_flags = acl_result['acl'][0]['flags']
    assert requested_flags == received_flags, str(acl_result)


"""
This next series of tests verifies that ACLs are being inherited correctly.
We first create a child dataset to verify that ACLs do not change unless
'traverse' is set.
"""


def test_12_prepare_recursive_tests(request):
    depends(request, ["HAS_NFS4_ACLS"], scope="session")
    call('pool.dataset.create', {'name': ACLTEST_SUBDATASET, 'acltype': 'NFSV4'})

    ssh(';'.join([
        f'mkdir -p /mnt/{ACLTEST_DATASET}/dir1/dir2',
        f'touch /mnt/{ACLTEST_DATASET}/dir1/testfile',
        f'touch /mnt/{ACLTEST_DATASET}/dir1/dir2/testfile'
    ]))


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
    acl_result = call('filesystem.getacl', f'/mnt/{ACLTEST_SUBDATASET}', True)
    init_acl = acl_result['acl'][0]['perms']

    call('filesystem.setacl', {
        'path': TEST_INFO['dataset_path'],
        'dacl': default_acl,
        'uid': 65534,
        'options': {'recursive': True}
    }, job=True)

    # Verify that it hasn't changed
    acl_result = call('filesystem.getacl', f'/mnt/{ACLTEST_SUBDATASET}', True)
    fin_acl = acl_result['acl'][0]['perms']
    assert init_acl == fin_acl, str(acl_result)

    # check on dir 1. Entry 1 should have INHERIT flag added, and
    # INHERIT_ONLY should be set to False at this depth.
    acl_result = call('filesystem.getacl', f'/mnt/{ACLTEST_DATASET}/dir1', False)
    theacl = acl_result['acl']
    assert theacl[0]['flags'] == expected_flags_0, results.text
    assert theacl[1]['flags'] == expected_flags_1, results.text

    # Verify that user was changed on subdirectory
    assert acl_result['uid'] == 65534, results.text

    # check on dir 2 - the no propogate inherit flag should have taken
    # effect and ACL length should be 1
    acl_result = call('filesystem.getacl', f'/mnt/{ACLTEST_DATASET}/dir1/dir2', False)
    theacl = acl_result['acl']
    assert theacl[0]['flags'] == expected_flags_0, results.text
    assert len(theacl) == 1, results.text

    # Verify that user was changed two deep
    assert acl_result['uid'] == 65534, results.text


def test_14_recursive_with_traverse(request):
    depends(request, ["HAS_NFS4_ACLS"])
    expected_flags_0 = INHERIT_FLAGS_BASIC.copy()
    expected_flags_0['INHERITED'] = True
    expected_flags_1 = base_flagset.copy()
    expected_flags_1['INHERITED'] = True

    call('filesystem.setacl', {
        'path': TEST_INFO['dataset_path'],
        'dacl': default_acl,
        'uid': 65534,
        'options': {'recursive': True, 'traverse': True}
    }, job=True)

    acl_result = call('filesystem.getacl', f'/mnt/{ACLTEST_SUBDATASET}', True)
    theacl = acl_result['acl']
    assert theacl[0]['flags'] == expected_flags_0, results.text
    assert theacl[1]['flags'] == expected_flags_1, results.text

    # Verify that user was changed
    assert acl_result['uid'] == 65534, results.text


def test_15_strip_acl_from_dataset(request):
    depends(request, ["HAS_NFS4_ACLS"])
    call('filesystem.setperm', {
        'path': TEST_INFO['dataset_path'],
        'mode': '777',
        'uid': 65534,
        'options': {'stripacl': True, 'recursive': True}
    }, job=True)

    assert call('filesystem.stat', f'/mnt/{ACLTEST_SUBDATASET}')['acl'] is True

    st =  call('filesystem.stat', f'/mnt/{ACLTEST_DATASET}')
    assert st['acl'] is False, str(st)
    assert oct(st['mode']) == '0o40777', str(st)

    st =  call('filesystem.stat', f'/mnt/{ACLTEST_DATASET}/dir1')
    assert st['acl'] is False, str(st)
    assert oct(st['mode']) == '0o40777', str(st)

    st =  call('filesystem.stat', f'/mnt/{ACLTEST_DATASET}/dir1/testfile')
    assert st['acl'] is False, str(st)
    assert oct(st['mode']) == '0o100777', str(st)


def test_20_delete_child_dataset(request):
    depends(request, ["HAS_NFS4_ACLS"])
    result = DELETE(
        f'/pool/dataset/id/{subdataset_url}/'
    )
    assert result.status_code == 200, result.text


@pytest.mark.dependency(name="HAS_TESTFILE")
def test_22_prep_testfile(request):
    depends(request, ["HAS_NFS4_ACLS"], scope="session")
    ssh(f'echo -n "CAT" >> /mnt/{ACLTEST_DATASET}/acltest.txt')


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
    depends(request, ["HAS_NFS4_ACLS", "HAS_TESTFILE"], scope="session")

    if perm == "FULL_DELETE":
        to_deny = {"DELETE_CHILD": True, "DELETE": True}
    else:
        to_deny = {perm: True}

    payload_acl = [{
        "tag": "USER",
        "id": TEST_INFO['user']['uid'],
        "type": "DENY",
        "perms": to_deny,
        "flags": {"BASIC": "INHERIT"}
    }]

    payload_acl.extend(function_testing_acl_deny)
    call('filesystem.setacl', {
        'path': TEST_INFO['dataset_path'],
        'dacl': payload_acl,
        'gid': 0, 'uid': 0,
        'options': {'recursive': True},
    }, job=True)

    if perm == "EXECUTE":
        cmd = f'cd /mnt/{ACLTEST_DATASET}'

    elif perm == "READ_ATTRIBUTES":
        cmd = f'stat /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm in ["DELETE", "DELETE_CHILD", "FULL_DELETE"]:
        cmd = f'rm -f /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "READ_DATA":
        cmd = f'cat /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_DATA":
        cmd = f'echo -n "CAT" >> /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_ATTRIBUTES":
        cmd = f'touch -a -m -t 201512180130.09 /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "READ_ACL":
        cmd = f'{getfaclcmd} /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_ACL":
        cmd = f'{setfaclcmd} -b /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_OWNER":
        cmd = f'chown {ACL_USER} /mnt/{ACLTEST_DATASET}/acltest.txt'

    else:
        # This should never happen.
        cmd = "touch /var/empty/ERROR"

    results = SSH_TEST(cmd, ACL_USER, ACL_PWD)
    """
    Per RFC5661 Section 6.2.1.3.2, deletion is permitted if either
    DELETE_CHILD is permitted on parent, or DELETE is permitted on
    file. This means that it should succeed when tested in isolation,
    but fail when combined.

    Unfortunately, this is implemented differenting in FreeBSD vs Linux.
    Former follows above recommendation, latter does not in that denial
    of DELETE on file takes precedence over allow of DELETE_CHILD.
    """
    errstr = f'cmd: {cmd}, res: {results["output"]}, to_deny {to_deny}'
    expected_delete = ["DELETE_CHILD"]
    if perm in expected_delete:
        assert results['result'] is True, errstr

        # unfortunately, we now need to recreate our testfile.
        ssh(f'echo -n "CAT" >> /mnt/{ACLTEST_DATASET}/acltest.txt')
    elif perm == "READ_ATTRIBUTES":
        assert results['result'] is True, errstr
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
    depends(request, ["HAS_NFS4_ACLS", "HAS_TESTFILE"], scope="session")

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
        "id": TEST_INFO['user']['uid'],
        "type": "ALLOW",
        "perms": to_allow,
        "flags": {"BASIC": "INHERIT"}
    }]
    payload_acl.extend(function_testing_acl_allow)

    call('filesystem.setacl', {
        'path': TEST_INFO['dataset_path'],
        'dacl': payload_acl,
        'gid': 65534, 'uid': 0,
        'options': {'recursive': True},
    }, job=True)

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
        cmd = f'{getfaclcmd} /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_ACL":
        cmd = f'{setfaclcmd} -x 0 /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_OWNER":
        cmd = f'chown {ACL_USER} /mnt/{ACLTEST_DATASET}/acltest.txt'

    else:
        # This should never happen.
        cmd = "touch /var/empty/ERROR"

    results = SSH_TEST(cmd, ACL_USER, ACL_PWD)
    errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
    assert results['result'] is True, errstr
    if perm in ["DELETE", "DELETE_CHILD"]:
        # unfortunately, we now need to recreate our testfile.
        ssh(f'echo -n "CAT" >> /mnt/{ACLTEST_DATASET}/acltest.txt')


@pytest.mark.parametrize('perm', IMPLEMENTED_ALLOW)
def test_25_test_acl_function_omit(perm, request):
    """
    Iterate through available permissions and add permissions
    required for an explicit ALLOW of that ACE from the previous
    test to succeed. This sets the stage to have success hinge
    on presence of the particular permissions bit. Then we omit
    it. This should result in a failure.
    """
    depends(request, ["HAS_NFS4_ACLS", "HAS_TESTFILE"], scope="session")

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
        "id": TEST_INFO['user']['uid'],
        "type": "ALLOW",
        "perms": to_allow,
        "flags": {"BASIC": "INHERIT"}
    }]

    payload_acl.extend(function_testing_acl_allow)

    call('filesystem.setacl', {
        'path': TEST_INFO['dataset_path'],
        'dacl': payload_acl,
        'gid': 65534, 'uid': 0,
        'options': {'recursive': True},
    }, job=True)

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
        cmd = f'{getfaclcmd} /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_ACL":
        cmd = f'{setfaclcmd} -x 0 /mnt/{ACLTEST_DATASET}/acltest.txt'

    elif perm == "WRITE_OWNER":
        cmd = f'chown {ACL_USER} /mnt/{ACLTEST_DATASET}/acltest.txt'

    else:
        # This should never happen.
        cmd = "touch /var/empty/ERROR"

    results = SSH_TEST(cmd, ACL_USER, ACL_PWD)
    errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
    assert results['result'] is False, errstr


@pytest.mark.parametrize('perm', IMPLEMENTED_ALLOW)
def test_25_test_acl_function_allow_restrict(perm, request):
    """
    Iterate through implemented allow permissions and verify that
    they grant no more permissions than intended. Some bits cannot
    be tested in isolation effectively using built in utilities.
    """
    depends(request, ["HAS_NFS4_ACLS", "HAS_TESTFILE"], scope="session")

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
        "id": TEST_INFO['user']['uid'],
        "type": "ALLOW",
        "perms": to_allow,
        "flags": {"BASIC": "INHERIT"}
    }]
    payload_acl.extend(function_testing_acl_allow)
    call('filesystem.setacl', {
        'path': TEST_INFO['dataset_path'],
        'dacl': payload_acl,
        'gid': 65534, 'uid': 0,
        'options': {'recursive': True},
    }, job=True)

    if "EXECUTE" not in tests_to_skip:
        cmd = f'cd /mnt/{ACLTEST_DATASET}'
        results = SSH_TEST(cmd, ACL_USER, ACL_PWD)
        errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
        assert results['result'] is False, errstr

    if "DELETE" not in tests_to_skip:
        cmd = f'rm /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, ACL_USER, ACL_PWD)
        errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
        assert results['result'] is False, errstr
        if results['result'] is True:
            # File must be re-created. Kernel ACL inheritance routine
            # will ensure that new file has right ACL.
            ssh(f'echo -n "CAT" >> /mnt/{ACLTEST_DATASET}/acltest.txt')

    if "READ_DATA" not in tests_to_skip:
        cmd = f'cat /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, ACL_USER, ACL_PWD)
        errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
        assert results['result'] is False, errstr

    if "WRITE_DATA" not in tests_to_skip:
        cmd = f'echo -n "CAT" >> /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, ACL_USER, ACL_PWD)
        errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
        assert results['result'] is False, errstr

    if "WRITE_ATTRIBUTES" not in tests_to_skip:
        cmd = f'touch -a -m -t 201512180130.09 /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, ACL_USER, ACL_PWD)
        errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
        assert results['result'] is False, errstr

    if "READ_ACL" not in tests_to_skip:
        cmd = f'{getfaclcmd} /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, ACL_USER, ACL_PWD)
        errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
        assert results['result'] is False, errstr

    if "WRITE_ACL" not in tests_to_skip:
        cmd = f'{setfaclcmd} -x 0 /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, ACL_USER, ACL_PWD)
        errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
        assert results['result'] is False, errstr

    if "WRITE_OWNER" not in tests_to_skip:
        cmd = f'chown {ACL_USER} /mnt/{ACLTEST_DATASET}/acltest.txt'
        results = SSH_TEST(cmd, ACL_USER, ACL_PWD)
        errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {to_allow}'
        assert results['result'] is False, errstr


def test_26_file_execute_deny(request):
    """
    Base permset with everyone@ FULL_CONTROL, but ace added on
    top explictly denying EXECUTE. Attempt to execute file should fail.
    """
    depends(request, ["HAS_NFS4_ACLS", "HAS_TESTFILE"], scope="session")
    payload_acl = [
        {
            "tag": "USER",
            "id": TEST_INFO['user']['uid'],
            "type": "DENY",
            "perms": {"EXECUTE": True},
            "flags": {"FILE_INHERIT": True}
        },
        {
            "tag": "USER",
            "id": TEST_INFO['user']['uid'],
            "type": "ALLOW",
            "perms": {"EXECUTE": True},
            "flags": {"BASIC": "NOINHERIT"}
        },
    ]
    payload_acl.extend(function_testing_acl_deny)
    call('filesystem.setacl', {
        'path': TEST_INFO['dataset_path'],
        'dacl': payload_acl,
        'gid': 0, 'uid': 0,
        'options': {'recursive': True},
    }, job=True)

    ssh(f'echo "echo CANARY" > /mnt/{ACLTEST_DATASET}/acltest.txt')

    cmd = f'/mnt/{ACLTEST_DATASET}/acltest.txt'
    results = SSH_TEST(cmd, ACL_USER, ACL_PWD)
    errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {payload_acl}'
    assert results['result'] is False, errstr


def test_27_file_execute_allow(request):
    """
    Verify that setting execute allows file execution. READ_DATA and
    READ_ATTRIBUTES are also granted beecause we need to be able to
    stat and read our test script.
    """
    depends(request, ["HAS_NFS4_ACLS", "HAS_TESTFILE"], scope="session")
    payload_acl = [
        {
            "tag": "USER",
            "id": TEST_INFO['user']['uid'],
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
            "id": TEST_INFO['user']['uid'],
            "type": "ALLOW",
            "perms": {"EXECUTE": True},
            "flags": {"BASIC": "NOINHERIT"}
        },
    ]
    payload_acl.extend(function_testing_acl_allow)
    call('filesystem.setacl', {
        'path': TEST_INFO['dataset_path'],
        'dacl': payload_acl,
        'gid': 0, 'uid': 0,
        'options': {'recursive': True},
    }, job=True)

    ssh(f'echo "echo CANARY" > /mnt/{ACLTEST_DATASET}/acltest.txt')

    cmd = f'/mnt/{ACLTEST_DATASET}/acltest.txt'
    results = SSH_TEST(cmd, ACL_USER, ACL_PWD)
    errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {payload_acl}'
    assert results['result'] is True, errstr


def test_28_file_execute_omit(request):
    """
    Grant user all permissions except EXECUTE. Attempt to execute
    file should fail.
    """
    depends(request, ["HAS_NFS4_ACLS", "HAS_TESTFILE"], scope="session")
    payload_acl = [
        {
            "tag": "USER",
            "id": TEST_INFO['user']['uid'],
            "type": "ALLOW",
            "perms": base_permset.copy(),
            "flags": {"FILE_INHERIT": True}
        },
        {
            "tag": "USER",
            "id": TEST_INFO['user']['uid'],
            "type": "ALLOW",
            "perms": {"EXECUTE": True},
            "flags": {"BASIC": "NOINHERIT"}
        },
    ]
    payload_acl.extend(function_testing_acl_allow)
    # at this point the user's ACE has all perms set
    # remove execute.
    payload_acl[0]['perms']['EXECUTE'] = False
    call('filesystem.setacl', {
        'path': TEST_INFO['dataset_path'],
        'dacl': payload_acl,
        'gid': 0, 'uid': 0,
        'options': {'recursive': True},
    }, job=True)

    ssh(f'echo "echo CANARY" > /mnt/{ACLTEST_DATASET}/acltest.txt')

    cmd = f'/mnt/{ACLTEST_DATASET}/acltest.txt'
    results = SSH_TEST(cmd, ACL_USER, ACL_PWD)
    errstr = f'cmd: {cmd}, res: {results["output"]}, to_allow {payload_acl}'
    assert results['result'] is False, errstr


def test_29_owner_restrictions(request):
    depends(request, ["HAS_NFS4_ACLS"], scope="session")

    payload_acl = [{
        "tag": "owner@",
        "id": -1,
        "type": "ALLOW",
        "perms": {"BASIC": "READ"},
        "flags": {"BASIC": "INHERIT"}
    }]
    call('filesystem.setacl', {
        'path': TEST_INFO['dataset_path'],
        'dacl': payload_acl,
        'gid': 0, 'uid': TEST_INFO['user']['uid'],
        'options': {'recursive': True},
    }, job=True)

    results = ssh(
        f'mkdir /mnt/{ACLTEST_DATASET}/dir1/dir_should_not_exist',
        complete_response=True, check=False,
        user=ACL_USER, password=ACL_PWD
    )

    assert results['result'] is False, str(results)

    results = ssh(
        f'touch /mnt/{ACLTEST_DATASET}/dir1/file_should_not_exist',
        complete_response=True, check=False,
        user=ACL_USER, password=ACL_PWD
    )

    assert results['result'] is False, str(results)


def test_30_acl_inherit_nested_dataset():
    with make_dataset("acl_test_inherit1", data={'share_type': 'SMB'}) as ds1:
        call('filesystem.add_to_acl', {
            'path': os.path.join('/mnt', ds1),
            'entries': [{'id_type': 'GROUP', 'id': 666, 'access': 'READ'}]
        }, job=True)

        acl1 = call('filesystem.getacl', os.path.join('/mnt', ds1))
        assert any(x['id'] == 666 for x in acl1['acl'])

        with pytest.raises(ValidationErrors):
            # ACL on parent dataset prevents adding APPS group to ACL. Fail.
            with make_dataset("acl_test_inherit1/acl_test_inherit2", data={'share_type': 'APPS'}):
                pass

        with make_dataset("acl_test_inherit1/acl_test_inherit2", data={'share_type': 'NFS'}) as ds2:
            acl2 = call('filesystem.getacl', os.path.join('/mnt', ds2))
            assert acl1['acltype'] == acl2['acltype']
            assert any(x['id'] == 666 for x in acl2['acl'])
