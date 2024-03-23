#!/usr/bin/env python3

# License: BSD

import sys
import os
import pytest
import stat
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, SSH_TEST, wait_on_job
from auto_config import ip, pool_name, user, password
from pytest_dependency import depends

pytestmark = [pytest.mark.fs, pytest.mark.slow]
MODE_DATASET = f'{pool_name}/modetest'
dataset_url = MODE_DATASET.replace('/', '%2F')

MODE_SUBDATASET = f'{pool_name}/modetest/sub1'
subdataset_url = MODE_SUBDATASET.replace('/', '%2F')

OWNER_BITS = {
    "OWNER_READ": stat.S_IRUSR,
    "OWNER_WRITE": stat.S_IWUSR,
    "OWNER_EXECUTE": stat.S_IXUSR,
}

GROUP_BITS = {
    "GROUP_READ": stat.S_IRGRP,
    "GROUP_WRITE": stat.S_IWGRP,
    "GROUP_EXECUTE": stat.S_IXGRP,
}

OTHER_BITS = {
    "OTHER_READ": stat.S_IROTH,
    "OTHER_WRITE": stat.S_IWOTH,
    "OTHER_EXECUTE": stat.S_IXOTH,
}

MODE = {**OWNER_BITS, **GROUP_BITS, **OTHER_BITS}

MODE_USER = "modetesting"
MODE_GROUP = "modetestgrp"
MODE_PWD = "modetesting"


def test_01_check_dataset_endpoint():
    assert isinstance(GET('/pool/dataset/').json(), list)


@pytest.mark.dependency(name="DATASET_CREATED")
def test_02_create_dataset(request):
    result = POST(
        '/pool/dataset/', {
            'name': MODE_DATASET
        }
    )
    assert result.status_code == 200, result.text


@pytest.mark.dependency(name="IS_TRIVIAL")
def test_03_verify_acl_is_trivial(request):
    depends(request, ["DATASET_CREATED"])
    results = POST('/filesystem/stat/', f'/mnt/{MODE_DATASET}')
    assert results.status_code == 200, results.text
    assert results.json()['acl'] is False, results.text


@pytest.mark.parametrize('mode_bit', MODE.keys())
def test_04_verify_setting_mode_bits_nonrecursive(request, mode_bit):
    """
    This test iterates through possible POSIX permissions bits and
    verifies that they are properly set on the remote server.
    """
    depends(request, ["IS_TRIVIAL"])
    new_mode = f"{MODE[mode_bit]:03o}"
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': [],
            'mode': new_mode,
            'group': 'nogroup',
            'user': 'nobody'
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    results = POST('/filesystem/stat/', f'/mnt/{MODE_DATASET}')
    assert results.status_code == 200, results.text
    server_mode = f"{stat.S_IMODE(results.json()['mode']):03o}"
    assert new_mode == server_mode, results.text


@pytest.mark.dependency(name="RECURSIVE_PREPARED")
def test_05_prepare_recursive_tests(request):
    depends(request, ["IS_TRIVIAL"], scope="session")
    result = POST(
        '/pool/dataset/', {
            'name': MODE_SUBDATASET
        }
    )
    assert result.status_code == 200, result.text

    cmd = f'mkdir -p /mnt/{MODE_DATASET}/dir1/dir2'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    cmd = f'touch /mnt/{MODE_DATASET}/dir1/dir2/testfile'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    results = POST('/filesystem/stat/', f'/mnt/{MODE_SUBDATASET}')
    assert results.status_code == 200, results.text
    current_mode = results.json()['mode']
    # new datasets should be created with 755 permissions"
    assert f"{stat.S_IMODE(current_mode):03o}" == "755", results.text


@pytest.mark.parametrize('mode_bit', MODE.keys())
def test_06_verify_setting_mode_bits_recursive_no_traverse(request, mode_bit):
    """
    Perform recursive permissions change and verify new mode written
    to files and subdirectories.
    """
    depends(request, ["RECURSIVE_PREPARED"])
    new_mode = f"{MODE[mode_bit]:03o}"
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': [],
            'mode': new_mode,
            'group': 'nogroup',
            'user': 'nobody',
            'options': {'recursive': True}
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    results = POST('/filesystem/stat/', f'/mnt/{MODE_DATASET}')
    assert results.status_code == 200, results.text
    server_mode = f"{stat.S_IMODE(results.json()['mode']):03o}"
    assert new_mode == server_mode, results.text

    results = POST('/filesystem/stat/', f'/mnt/{MODE_DATASET}/dir1/dir2')
    assert results.status_code == 200, results.text
    server_mode = f"{stat.S_IMODE(results.json()['mode']):03o}"
    assert new_mode == server_mode, results.text

    results = POST('/filesystem/stat/',
                   f'/mnt/{MODE_DATASET}/dir1/dir2/testfile')
    assert results.status_code == 200, results.text
    server_mode = f"{stat.S_IMODE(results.json()['mode']):03o}"
    assert new_mode == server_mode, results.text


def test_07_verify_mode_not_set_on_child_dataset(request):
    depends(request, ["RECURSIVE_PREPARED"])
    results = POST('/filesystem/stat/', f'/mnt/{MODE_SUBDATASET}')
    assert results.status_code == 200, results.text
    current_mode = results.json()['mode']
    # new datasets should be created with 755 permissions"
    assert f"{stat.S_IMODE(current_mode):03o}" == "755", results.text


def test_08_verify_traverse_to_child_dataset(request):
    depends(request, ["RECURSIVE_PREPARED"])
    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': [],
            'mode': 777,
            'group': 'nogroup',
            'user': 'nobody',
            'options': {'recursive': True, 'traverse': True}
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    results = POST('/filesystem/stat/', f'/mnt/{MODE_SUBDATASET}')
    assert results.status_code == 200, results.text
    current_mode = results.json()['mode']
    assert f"{stat.S_IMODE(current_mode):03o}" == "777", results.text


"""
Create user and group for testing function of POSIX permission bits.
"""


@pytest.mark.dependency(name="GROUP_CREATED")
def test_09_create_test_group(request):
    depends(request, ["IS_TRIVIAL"])
    global next_gid
    global groupid
    results = GET('/group/get_next_gid/')
    assert results.status_code == 200, results.text
    next_gid = results.json()
    global groupid
    payload = {
        "gid": next_gid,
        "name": MODE_GROUP,
    }
    results = POST("/group/", payload)
    assert results.status_code == 200, results.text
    groupid = results.json()


@pytest.mark.dependency(name="USER_CREATED")
def test_10_creating_shareuser_to_test_acls(request):
    depends(request, ["GROUP_CREATED"])
    global modeuser_id
    global next_uid
    results = GET('/user/get_next_uid/')
    assert results.status_code == 200, results.text
    next_uid = results.json()
    payload = {
        "username": MODE_USER,
        "full_name": "Mode User",
        "group_create": True,
        "password": MODE_PWD,
        "uid": next_uid,
        "groups": [groupid],
        "shell": '/usr/bin/bash',
        "ssh_password_enabled": True,
    }
    results = POST("/user/", payload)
    assert results.status_code == 200, results.text
    modeuser_id = results.json()


"""
Next series of tests are for correct behavior of POSIX permissions
"""


def dir_mode_check(mode_bit):
    if mode_bit.endswith("READ"):
        cmd = f'ls /mnt/{MODE_DATASET}'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is True, results['output']

        cmd = f'touch /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is False, results['output']

        cmd = f'cd /mnt/{MODE_DATASET}'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is False, results['output']

    elif mode_bit.endswith("WRITE"):
        cmd = f'ls /mnt/{MODE_DATASET}'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is False, results['output']

        cmd = f'touch /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is True, results['output']

        cmd = f'rm /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is True, results['output']

    elif mode_bit.endswith("EXECUTE"):
        cmd = f'ls /mnt/{MODE_DATASET}'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is False, results['output']

        # Ensure that file is deleted before trying to create
        cmd = f'rm /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, user, password, ip)

        cmd = f'touch /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is False, results['output']


def file_mode_check(mode_bit):
    if mode_bit.endswith("READ"):
        cmd = f'cat /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is True, results['output']
        assert results['stdout'].strip() == "echo CANARY", results['output']

        cmd = f'echo "FAIL" >> /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is False, results['output']

        cmd = f'/mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is False, results['output']

    elif mode_bit.endswith("WRITE"):
        cmd = f'cat /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is False, results['output']

        cmd = f'echo "SUCCESS" > /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is True, results['output']

        cmd = f'/mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is False, results['output']

        """
        Parent directory does not have write bit set. This
        means rm should fail even though WRITE is set for user.
        """
        cmd = f'rm /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is False, results['output']

        cmd = f'echo "echo CANARY" > /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, user, password, ip)
        assert results['result'] is True, results['output']

    elif mode_bit.endswith("EXECUTE"):
        cmd = f'cat /mnt/{MODE_DATASET}'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is False, results['output']

        cmd = f'echo "FAIL" > /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is False, results['output']


def file_mode_check_xor(mode_bit):
    """
    when this method is called, all permissions bits are set except for
    the one being tested.
    """
    if mode_bit.endswith("READ"):
        cmd = f'cat /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is False, results['output']

    elif mode_bit.endswith("WRITE"):
        cmd = f'echo "SUCCESS" > /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is False, results['output']

    elif mode_bit.endswith("EXECUTE"):
        cmd = f'/mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD, ip)
        assert results['result'] is False, results['output']


@pytest.mark.parametrize('mode_bit', OWNER_BITS.keys())
def test_11_test_directory_owner_bits_function_allow(mode_bit, request):
    """
    Verify mode behavior correct when it's the only bit set.
    In case of directory, Execute must be set concurrently with write
    in order to verify correct write behavior.
    """
    depends(request, ["USER_CREATED"], scope="session")
    new_mode = MODE[mode_bit]
    if new_mode == stat.S_IWUSR:
        new_mode |= stat.S_IXUSR

    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': [],
            'mode': f'{new_mode:03o}',
            'group': 'nogroup',
            'user': MODE_USER
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    if job_status['state'] != 'SUCCESS':
        return

    dir_mode_check(mode_bit)


@pytest.mark.parametrize('mode_bit', GROUP_BITS.keys())
def test_12_test_directory_group_bits_function_allow(mode_bit, request):
    """
    Verify mode behavior correct when it's the only bit set.
    In case of directory, Execute must be set concurrently with write
    in order to verify correct write behavior.
    """
    depends(request, ["USER_CREATED"], scope="session")
    new_mode = MODE[mode_bit]
    if new_mode == stat.S_IWGRP:
        new_mode |= stat.S_IXGRP

    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': [],
            'mode': f'{new_mode:03o}',
            'group': MODE_GROUP,
            'user': 'root'
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    if job_status['state'] != 'SUCCESS':
        return

    dir_mode_check(mode_bit)


@pytest.mark.parametrize('mode_bit', OTHER_BITS.keys())
def test_13_test_directory_other_bits_function_allow(mode_bit, request):
    """
    Verify mode behavior correct when it's the only bit set.
    In case of directory, Execute must be set concurrently with write
    in order to verify correct write behavior.
    """
    depends(request, ["USER_CREATED"], scope="session")
    new_mode = MODE[mode_bit]
    if new_mode == stat.S_IWOTH:
        new_mode |= stat.S_IXOTH

    result = POST(
        f'/pool/dataset/id/{dataset_url}/permission/', {
            'acl': [],
            'mode': f'{new_mode:03o}',
            'group': 'root',
            'user': 'root'
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    if job_status['state'] != 'SUCCESS':
        return

    dir_mode_check(mode_bit)


def test_14_setup_file_test(request):
    depends(request, ["USER_CREATED"], scope="session")
    result = POST(
        '/filesystem/setperm/', {
            'path': f'/mnt/{MODE_DATASET}',
            'mode': "001",
            'gid': 0,
            'uid': 0,
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    cmd = f'echo "echo CANARY" > /mnt/{MODE_DATASET}/canary'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@pytest.mark.parametrize('mode_bit', OWNER_BITS.keys())
def test_15_test_file_owner_bits_function_allow(mode_bit, request):
    """
    Verify mode behavior correct when it's the only bit set.
    """
    depends(request, ["USER_CREATED"], scope="session")
    new_mode = MODE[mode_bit]

    result = POST(
        '/filesystem/setperm/', {
            'path': f'/mnt/{MODE_DATASET}/canary',
            'mode': f'{new_mode:03o}',
            'gid': 0,
            'uid': next_uid
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    if job_status['state'] != 'SUCCESS':
        return

    file_mode_check(mode_bit)


@pytest.mark.parametrize('mode_bit', GROUP_BITS.keys())
def test_16_test_file_group_bits_function_allow(mode_bit, request):
    """
    Verify mode behavior correct when it's the only bit set.
    """
    depends(request, ["USER_CREATED"], scope="session")
    new_mode = MODE[mode_bit]

    result = POST(
        '/filesystem/setperm/', {
            'path': f'/mnt/{MODE_DATASET}/canary',
            'mode': f'{new_mode:03o}',
            'gid': next_gid,
            'uid': 0,
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    if job_status['state'] != 'SUCCESS':
        return

    file_mode_check(mode_bit)


@pytest.mark.parametrize('mode_bit', OTHER_BITS.keys())
def test_17_test_file_other_bits_function_allow(mode_bit, request):
    """
    Verify mode behavior correct when it's the only bit set.
    """
    depends(request, ["USER_CREATED"], scope="session")
    new_mode = MODE[mode_bit]

    result = POST(
        '/filesystem/setperm/', {
            'path': f'/mnt/{MODE_DATASET}/canary',
            'mode': f'{new_mode:03o}',
            'gid': 0,
            'uid': 0,
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    if job_status['state'] != 'SUCCESS':
        return

    file_mode_check(mode_bit)


@pytest.mark.parametrize('mode_bit', OWNER_BITS.keys())
def test_18_test_file_owner_bits_xor(mode_bit, request):
    """
    Verify mode behavior correct when it's the only bit set.
    """
    depends(request, ["USER_CREATED"], scope="session")
    new_mode = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
    new_mode = new_mode ^ MODE[mode_bit]

    result = POST(
        '/filesystem/setperm/', {
            'path': f'/mnt/{MODE_DATASET}/canary',
            'mode': f'{new_mode:03o}',
            'gid': 0,
            'uid': next_uid
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    if job_status['state'] != 'SUCCESS':
        return

    file_mode_check_xor(mode_bit)


@pytest.mark.parametrize('mode_bit', GROUP_BITS.keys())
def test_19_test_file_group_bits_xor(mode_bit, request):
    """
    Verify mode behavior correct when it's the only bit set.
    """
    depends(request, ["USER_CREATED"], scope="session")
    new_mode = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
    new_mode = new_mode ^ MODE[mode_bit]

    result = POST(
        '/filesystem/setperm/', {
            'path': f'/mnt/{MODE_DATASET}/canary',
            'mode': f'{new_mode:03o}',
            'gid': next_gid,
            'uid': 0
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    if job_status['state'] != 'SUCCESS':
        return

    file_mode_check_xor(mode_bit)


@pytest.mark.parametrize('mode_bit', OTHER_BITS.keys())
def test_20_test_file_other_bits_xor(mode_bit, request):
    """
    Verify mode behavior correct when it's the only bit set.
    """
    depends(request, ["USER_CREATED"], scope="session")
    new_mode = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
    new_mode = new_mode ^ MODE[mode_bit]

    result = POST(
        '/filesystem/setperm/', {
            'path': f'/mnt/{MODE_DATASET}/canary',
            'mode': f'{new_mode:03o}',
            'gid': 0,
            'uid': 0
        }
    )
    assert result.status_code == 200, result.text
    JOB_ID = result.json()
    job_status = wait_on_job(JOB_ID, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    if job_status['state'] != 'SUCCESS':
        return

    file_mode_check_xor(mode_bit)


def test_21_delete_child_dataset(request):
    depends(request, ["RECURSIVE_PREPARED"])
    result = DELETE(
        f'/pool/dataset/id/{subdataset_url}/'
    )
    assert result.status_code == 200, result.text


def test_22_delete_group(request):
    depends(request, ["GROUP_CREATED"])
    results = DELETE(f"/group/id/{groupid}/", {"delete_users": True})
    assert results.status_code == 200, results.text


def test_23_delete_user(request):
    depends(request, ["USER_CREATED"])
    results = DELETE(f"/user/id/{modeuser_id}/", {"delete_group": True})
    assert results.status_code == 200, results.text


def test_24_delete_dataset(request):
    depends(request, ["DATASET_CREATED"])
    result = DELETE(
        f'/pool/dataset/id/{dataset_url}/'
    )
    assert result.status_code == 200, result.text
