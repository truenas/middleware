#!/usr/bin/env python3

# License: BSD

import os
import pytest
import stat

from functions import SSH_TEST
from middlewared.test.integration.assets.account import user, group
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh
from time import sleep


MODE_DATASET_NAME = 'modetest'
MODE_SUBDATASET_NAME = 'modetest/sub1'

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


@pytest.fixture(scope='module')
def get_dataset():
    with dataset(MODE_DATASET_NAME) as ds:
        path = os.path.join('/mnt', ds)
        ssh(f'mkdir -p {path}/dir1/dir2')
        ssh(f'touch {path}/dir1/dir2/testfile')

        with dataset(MODE_SUBDATASET_NAME):
            yield ds


@pytest.fixture(scope='module')
def get_user():
    with group({"name": MODE_GROUP}) as g:
        with user({
            'username': MODE_USER,
            'full_name': MODE_USER,
            'password': MODE_PWD,
            'group_create': True,
            'shell': '/usr/bin/bash',
            'ssh_password_enabled': True,
            'groups': [g['id']]
        }) as u:
            yield u | {'group_gid': g['gid']}


@pytest.fixture(scope='function')
def setup_file(get_dataset):
    ds_path = os.path.join('/mnt', get_dataset)
    try:
        ssh(f'echo "echo CANARY" > {ds_path}/canary')
        yield
    finally:
        ssh(f'rm {ds_path}/canary', check=False)


def get_mode_octal(path):
    mode = call('filesystem.stat', path)['mode']
    return f"{stat.S_IMODE(mode):03o}"


@pytest.mark.dependency(name="IS_TRIVIAL")
def test_verify_acl_is_trivial(get_dataset):
    st = call('filesystem.stat', os.path.join('/mnt', get_dataset))
    assert st['acl'] is False


@pytest.mark.parametrize('mode_bit', MODE.keys())
def test_verify_setting_mode_bits_nonrecursive(get_dataset, mode_bit):
    """
    This test iterates through possible POSIX permissions bits and
    verifies that they are properly set on the remote server.
    """
    new_mode = f"{MODE[mode_bit]:03o}"
    path = os.path.join('/mnt', get_dataset)

    call('filesystem.setperm', {
        'path': path,
        'mode': new_mode,
        'uid': 65534,
        'gid': 65534
    }, job=True)

    server_mode = get_mode_octal(path)
    assert new_mode == server_mode


@pytest.mark.parametrize('mode_bit', MODE.keys())
def test_verify_setting_mode_bits_recursive_no_traverse(get_dataset, mode_bit):
    """
    Perform recursive permissions change and verify new mode written
    to files and subdirectories.
    """
    ds_path = os.path.join('/mnt', get_dataset)
    sub_ds_path = os.path.join(ds_path, 'sub1')

    new_mode = f"{MODE[mode_bit]:03o}"
    call('filesystem.setperm', {
        'path': ds_path,
        'mode': new_mode,
        'uid': 65534,
        'gid': 65534,
        'options': {'recursive': True}
    }, job=True)

    server_mode = get_mode_octal(ds_path)
    assert new_mode == server_mode

    server_mode = get_mode_octal(os.path.join(ds_path, 'dir1', 'dir2'))
    assert new_mode == server_mode

    server_mode = get_mode_octal(os.path.join(ds_path, 'dir1', 'dir2', 'testfile'))
    assert new_mode == server_mode

    # child dataset shouldn't be touched
    server_mode = get_mode_octal(sub_ds_path)
    assert server_mode == "755"


def test_verify_traverse_to_child_dataset(get_dataset):
    ds_path = os.path.join('/mnt', get_dataset)
    sub_ds_path = os.path.join(ds_path, 'sub1')

    call('filesystem.setperm', {
        'path': ds_path,
        'mode': '777',
        'uid': 65534,
        'gid': 65534,
        'options': {'recursive': True, 'traverse': True}
    }, job=True)

    server_mode = get_mode_octal(sub_ds_path)
    assert server_mode == "777"


def dir_mode_check(mode_bit, MODE_DATASET):
    if mode_bit.endswith("READ"):
        cmd = f'ls /mnt/{MODE_DATASET}'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is True, results['output']

        cmd = f'touch /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is False, results['output']

        cmd = f'cd /mnt/{MODE_DATASET}'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is False, results['output']

    elif mode_bit.endswith("WRITE"):
        cmd = f'ls /mnt/{MODE_DATASET}'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is False, results['output']

        # Ensure that file is deleted before trying to create
        ssh(f'rm /mnt/{MODE_DATASET}/canary', check=False)

        cmd = f'touch /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is True, results['output']

        cmd = f'rm /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is True, results['output']

    elif mode_bit.endswith("EXECUTE"):
        cmd = f'ls /mnt/{MODE_DATASET}'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is False, results['output']

        # Ensure that file is deleted before trying to create
        ssh(f'rm /mnt/{MODE_DATASET}/canary', check=False)

        cmd = f'touch /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is False, results['output']


def file_mode_check(mode_bit, MODE_DATASET):
    if mode_bit.endswith("READ"):
        cmd = f'cat /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is True, results['output']
        assert results['stdout'].strip() == "echo CANARY", results['output']

        cmd = f'echo "FAIL" >> /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is False, results['output']

        cmd = f'/mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is False, results['output']

    elif mode_bit.endswith("WRITE"):
        cmd = f'cat /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is False, results['output']

        cmd = f'echo "SUCCESS" > /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is True, results['output']

        cmd = f'/mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is False, results['output']

        """
        Parent directory does not have write bit set. This
        means rm should fail even though WRITE is set for user.
        """
        cmd = f'rm /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is False, results['output']

        ssh(f'echo "echo CANARY" > /mnt/{MODE_DATASET}/canary')

    elif mode_bit.endswith("EXECUTE"):
        cmd = f'cat /mnt/{MODE_DATASET}'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is False, results['output']

        cmd = f'echo "FAIL" > /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is False, results['output']


def file_mode_check_xor(mode_bit, MODE_DATASET):
    """
    when this method is called, all permissions bits are set except for
    the one being tested.
    """
    if mode_bit.endswith("READ"):
        cmd = f'cat /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is False, results['output']

    elif mode_bit.endswith("WRITE"):
        cmd = f'echo "SUCCESS" > /mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is False, results['output']

    elif mode_bit.endswith("EXECUTE"):
        cmd = f'/mnt/{MODE_DATASET}/canary'
        results = SSH_TEST(cmd, MODE_USER, MODE_PWD)
        assert results['result'] is False, results['output']


@pytest.mark.parametrize('mode_bit', OWNER_BITS.keys())
def test_directory_owner_bits_function_allow(mode_bit, get_dataset, get_user):
    """
    Verify mode behavior correct when it's the only bit set.
    In case of directory, Execute must be set concurrently with write
    in order to verify correct write behavior.
    """
    ds_path = os.path.join('/mnt', get_dataset)
    new_mode = MODE[mode_bit]
    if new_mode == stat.S_IWUSR:
        new_mode |= stat.S_IXUSR

    call('filesystem.setperm', {
        'path': ds_path,
        'mode': f'{new_mode:03o}',
        'uid': get_user['uid'],
        'gid': 65534,
    }, job=True)

    dir_mode_check(mode_bit, get_dataset)


@pytest.mark.parametrize('mode_bit', GROUP_BITS.keys())
def test_directory_group_bits_function_allow(mode_bit, get_dataset, get_user):
    """
    Verify mode behavior correct when it's the only bit set.
    In case of directory, Execute must be set concurrently with write
    in order to verify correct write behavior.
    """
    ds_path = os.path.join('/mnt', get_dataset)

    new_mode = MODE[mode_bit]
    if new_mode == stat.S_IWGRP:
        new_mode |= stat.S_IXGRP

    call('filesystem.setperm', {
        'path': ds_path,
        'mode': f'{new_mode:03o}',
        'uid': 0,
        'gid': get_user['group_gid'],
    }, job=True)

    dir_mode_check(mode_bit, get_dataset)


@pytest.mark.parametrize('mode_bit', OTHER_BITS.keys())
def test_directory_other_bits_function_allow(mode_bit, get_dataset, setup_file):
    """
    Verify mode behavior correct when it's the only bit set.
    In case of directory, Execute must be set concurrently with write
    in order to verify correct write behavior.
    """
    ds_path = os.path.join('/mnt', get_dataset)

    new_mode = MODE[mode_bit]
    if new_mode == stat.S_IWOTH:
        new_mode |= stat.S_IXOTH

    call('filesystem.setperm', {
        'path': ds_path,
        'mode': f'{new_mode:03o}',
        'uid': 0,
        'gid': 0,
    }, job=True)

    sleep(5)
    dir_mode_check(mode_bit, get_dataset)


def test_setup_dataset_perm(get_dataset):
    """ Allow execute permission on dataset mountpoint to facilitate file testing """
    ds_path = os.path.join('/mnt', get_dataset)
    call('filesystem.setperm', {
        'path': ds_path,
        'mode': '001',
        'uid': 0,
        'gid': 0,
    }, job=True)


@pytest.mark.parametrize('mode_bit', OWNER_BITS.keys())
def test_file_owner_bits_function_allow(mode_bit, get_dataset, get_user, setup_file):
    """
    Verify mode behavior correct when it's the only bit set.
    """
    ds_path = os.path.join('/mnt', get_dataset)
    new_mode = MODE[mode_bit]

    call('filesystem.setperm', {
        'path': os.path.join(ds_path, 'canary'),
        'mode': f'{new_mode:03o}',
        'uid': get_user['uid'],
        'gid': 0,
    }, job=True)

    file_mode_check(mode_bit, get_dataset)


@pytest.mark.parametrize('mode_bit', GROUP_BITS.keys())
def test_file_group_bits_function_allow(mode_bit, get_dataset, get_user, setup_file):
    """
    Verify mode behavior correct when it's the only bit set.
    """
    ds_path = os.path.join('/mnt', get_dataset)
    new_mode = MODE[mode_bit]

    call('filesystem.setperm', {
        'path': os.path.join(ds_path, 'canary'),
        'mode': f'{new_mode:03o}',
        'gid': get_user['group_gid'],
        'uid': 0,
    }, job=True)

    file_mode_check(mode_bit, get_dataset)


@pytest.mark.parametrize('mode_bit', OTHER_BITS.keys())
def test_file_other_bits_function_allow(mode_bit, get_dataset, get_user, setup_file):
    """
    Verify mode behavior correct when it's the only bit set.
    """
    ds_path = os.path.join('/mnt', get_dataset)
    new_mode = MODE[mode_bit]

    call('filesystem.setperm', {
        'path': os.path.join(ds_path, 'canary'),
        'mode': f'{new_mode:03o}',
        'gid': 0,
        'uid': 0,
    }, job=True)

    file_mode_check(mode_bit, get_dataset)


@pytest.mark.parametrize('mode_bit', OWNER_BITS.keys())
def test_file_owner_bits_xor(mode_bit, get_dataset, get_user, setup_file):
    """
    Verify mode behavior correct when it's the only bit set.
    """
    ds_path = os.path.join('/mnt', get_dataset)
    new_mode = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
    new_mode = new_mode ^ MODE[mode_bit]

    call('filesystem.setperm', {
        'path': os.path.join(ds_path, 'canary'),
        'mode': f'{new_mode:03o}',
        'gid': 0,
        'uid': get_user['uid'],
    }, job=True)

    file_mode_check_xor(mode_bit, get_dataset)


@pytest.mark.parametrize('mode_bit', GROUP_BITS.keys())
def test_file_group_bits_xor(mode_bit, get_dataset, get_user, setup_file):
    """
    Verify mode behavior correct when it's the only bit set.
    """
    ds_path = os.path.join('/mnt', get_dataset)
    new_mode = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
    new_mode = new_mode ^ MODE[mode_bit]

    call('filesystem.setperm', {
        'path': os.path.join(ds_path, 'canary'),
        'mode': f'{new_mode:03o}',
        'gid': get_user['group_gid'],
        'uid': 0,
    }, job=True)

    file_mode_check_xor(mode_bit, get_dataset)


@pytest.mark.parametrize('mode_bit', OTHER_BITS.keys())
def test_file_other_bits_xor(mode_bit, get_dataset, get_user, setup_file):
    """
    Verify mode behavior correct when it's the only bit set.
    """
    ds_path = os.path.join('/mnt', get_dataset)
    new_mode = stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
    new_mode = new_mode ^ MODE[mode_bit]

    call('filesystem.setperm', {
        'path': os.path.join(ds_path, 'canary'),
        'mode': f'{new_mode:03o}',
        'gid': 0,
        'uid': 0,
    }, job=True)

    file_mode_check_xor(mode_bit, get_dataset)
