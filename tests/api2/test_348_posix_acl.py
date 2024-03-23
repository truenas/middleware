#!/usr/bin/env python3

# License: BSD

import sys
import os
import enum
import pytest
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, SSH_TEST, wait_on_job
from auto_config import ip, pool_name, user, password
from pytest_dependency import depends

pytestmark = [pytest.mark.fs, pytest.mark.slow]
ACLTEST_DATASET = f'{pool_name}/posixacltest'
DATASET_URL = ACLTEST_DATASET.replace('/', '%2F')

ACLTEST_SUBDATASET = f'{pool_name}/posixacltest/sub1'
SUBDATASET_URL = ACLTEST_SUBDATASET.replace('/', '%2F')

permset_empty = {"READ": False, "WRITE": False, "EXECUTE": False}
permset_full = {"READ": True, "WRITE": True, "EXECUTE": True}

tags = {
    "USER_OBJ": {"mask_required": False},
    "GROUP_OBJ": {"mask_required": False},
    "MASK": {"mask_required": False},
    "USER": {"mask_required": True},
    "GROUP": {"mask_required": True},
    "OTHER": {"mask_required": False},
}


class ACLBrand(enum.Enum):
    ACCESS = enum.auto()
    DEFAULT = enum.auto()

    def getacl(self, perms=None):
        """
        Default to 770 unless permissions explicitly specified.
        """

        out = [
            {
                "tag": "USER_OBJ",
                "id": -1,
                "perms": perms if perms else permset_full.copy(),
                "default": self.name == "DEFAULT",
            },
            {
                "tag": "GROUP_OBJ",
                "id": -1,
                "perms": perms if perms else permset_full.copy(),
                "default": self.name == "DEFAULT",
            },
            {
                "tag": "OTHER",
                "id": -1,
                "perms": perms if perms else permset_empty.copy(),
                "default": self.name == "DEFAULT",
            }
        ]
        return out


default_acl = ACLBrand.ACCESS.getacl()

JOB_ID = None


def test_01_check_dataset_endpoint():
    assert isinstance(GET('/pool/dataset/').json(), list)


@pytest.mark.dependency(name="DATASET_CREATED")
def test_02_create_dataset(request):
    result = POST(
        '/pool/dataset/', {
            'name': ACLTEST_DATASET,
            'acltype': 'POSIX',
            'aclmode': 'DISCARD',
        }
    )
    assert result.status_code == 200, result.text


@pytest.mark.dependency(name="HAS_POSIX_ACLS")
def test_03_get_acltype(request):
    """
    This test verifies that our dataset was created
    successfully and that the acltype is POSIX1E,
    which should be default for a "generic" dataset.
    """
    depends(request, ["DATASET_CREATED"])
    global results
    payload = {
        'path': f'/mnt/{ACLTEST_DATASET}',
    }
    result = POST('/filesystem/getacl/', payload)
    assert result.status_code == 200, results.text
    assert result.json()['acltype'] == 'POSIX1E', results.text


def test_04_basic_set_acl_for_dataset(request):
    """
    This test verifies that we can set a trivial
    POSIX1E ACL through the setacl endpoint.
    """
    depends(request, ["HAS_POSIX_ACLS"])
    payload = {
        'path': f'/mnt/{ACLTEST_DATASET}',
        'dacl': ACLBrand.ACCESS.getacl(),
        'gid': 65534,
        'uid': 65534,
        'acltype': 'POSIX1E'
    }

    result = POST('/filesystem/setacl/', payload)
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_05_get_filesystem_getacl(request):
    depends(request, ["HAS_POSIX_ACLS"])
    global results
    payload = {
        'path': f'/mnt/{ACLTEST_DATASET}',
    }
    results = POST('/filesystem/getacl/', payload)
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('key', ['tag', 'perms'])
def test_06_verify_filesystem_getacl(request, key):
    """
    This test verifies that our payload in above test was
    correctly applied and that the resulting ACL is reported as trivial.
    """
    depends(request, ["HAS_POSIX_ACLS"])
    assert results.json()['acl'][0][key] == default_acl[0][key], results.text
    assert results.json()['acl'][1][key] == default_acl[1][key], results.text
    assert results.json()['acl'][2][key] == default_acl[2][key], results.text
    assert results.json()['trivial'], results.text


def test_07_verify_setacl_chown(request):
    """
    This test verifies that the UID and GID from setacl
    payload were applied correctly. When a dataset is created,
    UID and GID will be 0.
    """
    depends(request, ["HAS_POSIX_ACLS"])
    assert results.json()['uid'] == 65534, results.text
    assert results.json()['gid'] == 65534, results.text


"""
At this point very basic functionality of API endpoint is verified.
Proceed to more rigorous testing of permissions.
"""


@pytest.mark.parametrize('perm', ["READ", "WRITE", "EXECUTE"])
def test_08_set_perms(request, perm):
    """
    Validation that READ, WRITE, EXECUTE are set correctly via endpoint.
    OTHER entry is used for this purpose.
    """
    depends(request, ["HAS_POSIX_ACLS"])
    payload = {
        'path': f'/mnt/{ACLTEST_DATASET}',
        'dacl': ACLBrand.ACCESS.getacl(),
        'acltype': 'POSIX1E'
    }
    payload['dacl'][2]['perms'][perm] = True
    result = POST('/filesystem/setacl/', payload)
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    results = POST('/filesystem/getacl/',
                   {'path': f'/mnt/{ACLTEST_DATASET}'})
    assert results.status_code == 200, results.text
    received_perms = results.json()['acl'][2]['perms']
    assert received_perms[perm], results.text


@pytest.mark.parametrize('tag', tags.keys())
def test_09_set_tags(request, tag):
    """
    Validation that entries for all tag types can be set correctly.
    In case of USER_OBJ, GROUP_OBJ, and OTHER, the existing entry
    is modified to match our test permset. USER and GROUP (named)
    entries are set for id 1000 (user / group need not exist for
    this to succeed). Named entries require an additional mask entry.
    """
    depends(request, ["HAS_POSIX_ACLS"])
    test_permset = {"READ": True, "WRITE": False, "EXECUTE": True}
    must_add = True

    payload = {
        'path': f'/mnt/{ACLTEST_DATASET}',
        'dacl': ACLBrand.ACCESS.getacl(),
        'acltype': 'POSIX1E'
    }
    for entry in payload['dacl']:
        if entry['tag'] == tag:
            entry['perms'] = test_permset
            must_add = False
            break

    if must_add:
        new_entry = {
            'tag': tag,
            'perms': test_permset,
            'id': 1000,
            'default': False,
        }
        if tag == 'MASK':
            new_entry['id'] = -1
            # POSIX ACLs are quite particular about
            # ACE ordering. We do this on backend.
            # MASK comes before OTHER.
            payload['dacl'].insert(2, new_entry)
        elif tag == 'USER':
            payload['dacl'].insert(1, new_entry)
        elif tag == 'GROUP':
            payload['dacl'].insert(2, new_entry)

    if tags[tag]['mask_required']:
        new_entry = {
            'tag': "MASK",
            'perms': test_permset,
            'id': -1,
            'default': False,
        }
        payload['dacl'].insert(3, new_entry)

    results = POST('/filesystem/setacl/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    results = POST('/filesystem/getacl/',
                   {'path': f'/mnt/{ACLTEST_DATASET}'})
    assert results.status_code == 200, results.text
    new_acl = results.json()['acl']
    assert payload['dacl'] == new_acl, results.text


@pytest.mark.parametrize('tag', tags.keys())
def test_10_set_tags_default(request, tag):
    """
    Validation that entries for all tag types can be set correctly.
    In case of USER_OBJ, GROUP_OBJ, and OTHER, the existing entry
    is modified to match our test permset. USER and GROUP (named)
    entries are set for id 1000 (user / group need not exist for
    this to succeed). Named entries require an additional mask entry.
    This particular test covers "default" entries in POSIX1E ACL.
    """
    depends(request, ["HAS_POSIX_ACLS"])
    test_permset = {"READ": True, "WRITE": False, "EXECUTE": True}
    must_add = True

    payload = {
        'path': f'/mnt/{ACLTEST_DATASET}',
        'dacl': ACLBrand.ACCESS.getacl(),
        'acltype': 'POSIX1E',
    }
    default = ACLBrand.DEFAULT.getacl()
    for entry in default:
        if entry['tag'] == tag:
            entry['perms'] = test_permset
            must_add = False

    if must_add:
        new_entry = {
            'tag': tag,
            'perms': test_permset,
            'id': 1000,
            'default': True,
        }
        if tag == 'MASK':
            new_entry['id'] = -1
            # POSIX ACLs are quite particular about
            # ACE ordering. We do this on backend.
            # MASK comes before OTHER.
            default.insert(2, new_entry)
        elif tag == 'USER':
            default.insert(1, new_entry)
        elif tag == 'GROUP':
            default.insert(2, new_entry)

    if tags[tag]['mask_required']:
        new_entry = {
            'tag': "MASK",
            'perms': test_permset,
            'id': -1,
            'default': True,
        }
        default.insert(3, new_entry)

    payload['dacl'].extend(default)
    results = POST('/filesystem/setacl/', payload)
    assert results.status_code == 200, results.text
    JOB_ID = results.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    results = POST('/filesystem/getacl/',
                   {'path': f'/mnt/{ACLTEST_DATASET}'})
    assert results.status_code == 200, results.text
    new_acl = results.json()
    assert payload['dacl'] == new_acl['acl'], results.text
    assert new_acl['trivial'] is False, results.text


def test_11_non_recursive_acl_strip(request):
    """
    Verify that non-recursive ACL strip works correctly.
    We do this by checking result of subsequent getacl
    request on the path (it should report that it is "trivial").
    """
    depends(request, ["HAS_POSIX_ACLS"])

    payload = {
        'path': f'/mnt/{ACLTEST_DATASET}',
        'dacl': [],
        'acltype': 'POSIX1E',
        'options': {'stripacl': True},
    }
    result = POST('/filesystem/setacl/', payload)
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    results = POST('/filesystem/getacl/',
                   {'path': f'/mnt/{ACLTEST_DATASET}'})
    assert results.status_code == 200, results.text
    new_acl = results.json()
    assert new_acl['trivial'], results.text


"""
This next series of tests verifies that ACLs are being inherited correctly.
We first create a child dataset to verify that ACLs do not change unless
'traverse' is set.
"""


def test_12_prepare_recursive_tests(request):
    depends(request, ["HAS_POSIX_ACLS"], scope="session")
    result = POST(
        '/pool/dataset/', {
            'name': ACLTEST_SUBDATASET,
            'acltype': 'POSIX',
            'aclmode': 'DISCARD',
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
    """
    Test that ACL is recursively applied correctly, but does
    not affect mountpoint of child dataset.

    In this case, access ACL will have 750 for dataset mountpoint,
    and default ACL will have 777. Recusively applying will grant
    777 for access and default.
    """
    depends(request, ["HAS_POSIX_ACLS"])

    payload = {
        'path': f'/mnt/{ACLTEST_DATASET}',
        'gid': 65534,
        'uid': 65534,
        'dacl': ACLBrand.ACCESS.getacl(),
        'acltype': 'POSIX1E',
        'options': {'recursive': True},
    }
    new_perms = {"READ": True, "WRITE": True, "EXECUTE": True}
    default = ACLBrand.DEFAULT.getacl(new_perms)

    payload['dacl'].extend(default)
    result = POST('/filesystem/setacl/', payload)

    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    # Verify that it hasn't changed. Should still report as trivial.
    results = POST('/filesystem/getacl/',
                   {'path': f'/mnt/{ACLTEST_SUBDATASET}'})
    assert results.status_code == 200, results.text
    new_acl = results.json()
    assert new_acl['trivial'], results.text

    results2 = POST('/filesystem/getacl/',
                    {'path': f'/mnt/{ACLTEST_DATASET}/dir1'})

    assert results2.status_code == 200, results.text
    # Verify that user was changed on subdirectory
    assert results2.json()['uid'] == 65534, results.text

    assert results2.status_code == 200, results.text
    theacl = results2.json()
    assert theacl['trivial'] is False, results.text
    for entry in theacl['acl']:
        assert entry['perms'] == new_perms, results.text


def test_14_recursive_with_traverse(request):
    """
    This test verifies that setting `traverse = True`
    will allow setacl operation to cross mountpoints.
    """
    depends(request, ["HAS_POSIX_ACLS"])

    payload = {
        'gid': 65534,
        'uid': 65534,
        'path': f'/mnt/{ACLTEST_DATASET}',
        'dacl': ACLBrand.ACCESS.getacl(),
        'acltype': 'POSIX1E',
        'options': {'recursive': True, 'traverse': True},
    }
    default = ACLBrand.DEFAULT.getacl({"READ": True, "WRITE": True, "EXECUTE": True})

    payload['dacl'].extend(default)
    result = POST('/filesystem/setacl/', payload)

    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    results = POST('/filesystem/getacl/',
                   {'path': f'/mnt/{ACLTEST_SUBDATASET}'})
    assert results.status_code == 200, results.text

    new_acl = results.json()
    assert new_acl['trivial'] is False, results.text

    # Verify that user was changed
    assert results.json()['uid'] == 65534, results.text


def test_15_strip_acl_from_dataset(request):
    """
    Strip ACL via pool.dataset.permission endpoint.
    This should work even for POSIX1E ACLs.
    """
    depends(request, ["HAS_POSIX_ACLS"])
    result = POST(
        f'/pool/dataset/id/{DATASET_URL}/permission/', {
            'acl': [],
            'mode': '777',
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
    depends(request, ["HAS_POSIX_ACLS"])
    results = POST('/filesystem/stat/', f'/mnt/{ACLTEST_SUBDATASET}')
    assert results.status_code == 200, results.text
    assert results.json()['acl'] is True, results.text


def test_17_filesystem_acl_is_removed_mountpoint(request):
    depends(request, ["HAS_POSIX_ACLS"])
    results = POST('/filesystem/stat/', f'/mnt/{ACLTEST_DATASET}')
    assert results.status_code == 200, results.text
    assert results.json()['acl'] is False, results.text
    assert oct(results.json()['mode']) == '0o40777', results.text


def test_18_filesystem_acl_is_removed_subdir(request):
    depends(request, ["HAS_POSIX_ACLS"])
    results = POST('/filesystem/stat/', f'/mnt/{ACLTEST_DATASET}/dir1')
    assert results.status_code == 200, results.text
    assert results.json()['acl'] is False, results.text
    assert oct(results.json()['mode']) == '0o40777', results.text


def test_19_filesystem_acl_is_removed_file(request):
    depends(request, ["HAS_POSIX_ACLS"])
    results = POST('/filesystem/stat/',
                   f'/mnt/{ACLTEST_DATASET}/dir1/testfile')
    assert results.status_code == 200, results.text
    assert results.json()['acl'] is False, results.text
    assert oct(results.json()['mode']) == '0o100777', results.text


def test_20_delete_child_dataset(request):
    depends(request, ["HAS_POSIX_ACLS"])
    result = DELETE(
        f'/pool/dataset/id/{SUBDATASET_URL}/'
    )
    assert result.status_code == 200, result.text


def test_30_delete_dataset(request):
    result = DELETE(
        f'/pool/dataset/id/{DATASET_URL}/'
    )
    assert result.status_code == 200, result.text
