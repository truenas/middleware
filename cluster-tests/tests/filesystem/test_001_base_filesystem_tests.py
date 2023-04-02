import pytest
import stat

from config import CLUSTER_INFO, CLUSTER_IPS, TIMEOUTS
from utils import make_request, ssh_test, wait_on_job
from exceptions import JobTimeOut
from pytest_dependency import depends
from time import sleep

FUSE_OP_TIMEOUT = TIMEOUTS['FUSE_OP_TIMEOUT']
LOCAL_PATH = f'/cluster/{CLUSTER_INFO["GLUSTER_VOLUME"]}/filesystem_01'
CLUSTER_PATH = f'CLUSTER:{CLUSTER_INFO["GLUSTER_VOLUME"]}/filesystem_01'
testfiles = [
    ('file01', False),
    ('dir01', True),
    ('dir01/file02', False),
]


@pytest.mark.parametrize('ip', CLUSTER_IPS)
@pytest.mark.dependency(name="FS_BASIC_GLUSTER_VOLUME_MOUNTED")
def test_001_volume_is_mounted(ip):
    url = f'http://{ip}/api/v2.0/gluster/fuse/is_mounted/'
    payload = {"name": CLUSTER_INFO["GLUSTER_VOLUME"]}
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text
    assert res.json() is True, res.text


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_002_enable_and_start_ssh(ip, request):
    depends(request, ['FS_BASIC_GLUSTER_VOLUME_MOUNTED'])

    url = f'http://{ip}/api/v2.0/user?username=root'
    res = make_request('get', url)
    assert res.status_code == 200, res.text
    root = res.json()[0]

    payload = {"ssh_password_enabled": True}
    url = f'http://{ip}/api/v2.0/user/id/{root["id"]}'
    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text

    url = f'http://{ip}/api/v2.0/service/start'
    payload = {"service": "ssh"}
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text


@pytest.mark.dependency(name="FS_BASIC_TEST_FILES_CREATED")
def test_003_create_test_files(request):
    depends(request, ['FS_BASIC_GLUSTER_VOLUME_MOUNTED'])

    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/filesystem/mkdir/'
    res = make_request('post', url, data=CLUSTER_PATH)
    assert res.status_code == 200, res.text

    cmd = f'touch {LOCAL_PATH}/file01;'
    cmd += f'mkdir {LOCAL_PATH}/dir01;'
    cmd += f'touch {LOCAL_PATH}/dir01/file02'
    res = ssh_test(CLUSTER_IPS[0], cmd)
    assert res['result'], res['stderr']


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_004_filesystem_stat(ip, request):
    depends(request, ['FS_BASIC_TEST_FILES_CREATED'])

    for f, isdir in testfiles:
        payload = f'{CLUSTER_PATH}/{f}'
        url = f'http://{CLUSTER_IPS[1]}/api/v2.0/filesystem/stat/'
        res = make_request('post', url, data=payload)
        assert res.status_code == 200, res.text
        data = res.json()
        assert stat.S_ISDIR(data['mode']) == isdir, f'file: {f}, data: {data}'


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_005_filesystem_listdir(ip, request):
    depends(request, ['FS_BASIC_TEST_FILES_CREATED'])

    payload = {'path': f'{CLUSTER_PATH}/'}
    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/filesystem/listdir/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data) == 2, data
    names = [x['name'] for x in data]
    assert 'dir01' in names, data
    assert 'file01' in names, data

    payload = {'path': f'{CLUSTER_PATH}/dir01'}
    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/filesystem/listdir/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert len(data) == 1, data
    names = [x['name'] for x in data]
    assert 'file02' in names, data


def test_006_filesystem_chown_non_recursive(request):
    depends(request, ['FS_BASIC_TEST_FILES_CREATED'])

    payload = {
        "path": CLUSTER_PATH,
        "uid": 1000,
        "options": {"recursive": False}
    }
    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/filesystem/chown/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text

    try:
        status = wait_on_job(res.json(), CLUSTER_IPS[1], FUSE_OP_TIMEOUT)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status

    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/filesystem/stat/'
    res = make_request('post', url, data=CLUSTER_PATH)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data['uid'] == 1000
    assert data['gid'] == 0

    payload = {'path': CLUSTER_PATH}
    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/filesystem/listdir/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    for entry in data:
        assert entry['uid'] == 0
        assert entry['gid'] == 0


def test_007_filesystem_chown_recursive(request):
    depends(request, ['FS_BASIC_TEST_FILES_CREATED'])

    payload = {
        "path": CLUSTER_PATH,
        "uid": 2000,
        "options": {"recursive": True}
    }
    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/filesystem/chown/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text

    try:
        status = wait_on_job(res.json(), CLUSTER_IPS[1], FUSE_OP_TIMEOUT)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status

    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/filesystem/stat/'
    res = make_request('post', url, data=CLUSTER_PATH)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data['uid'] == 2000
    assert data['gid'] == 0

    payload = {'path': CLUSTER_PATH}
    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/filesystem/listdir/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    for entry in data:
        assert entry['uid'] == 2000
        assert entry['gid'] == 0


def test_008_filesystem_reset_owner(request):
    depends(request, ['FS_BASIC_TEST_FILES_CREATED'])

    payload = {
        "path": CLUSTER_PATH,
        "uid": 0,
        "options": {"recursive": True}
    }
    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/filesystem/chown/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text
    try:
        status = wait_on_job(res.json(), CLUSTER_IPS[1], FUSE_OP_TIMEOUT)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status

    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/filesystem/stat/'
    res = make_request('post', url, data=CLUSTER_PATH)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data['uid'] == 0
    assert data['gid'] == 0


def test_009_filesystem_setperm_nonrecursive(request):
    depends(request, ['FS_BASIC_TEST_FILES_CREATED'])
    payload = {
        "path": CLUSTER_PATH,
        "mode": "777",
        "options": {"recursive": False}
    }
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/filesystem/setperm/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text

    try:
        status = wait_on_job(res.json(), CLUSTER_IPS[0], FUSE_OP_TIMEOUT)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status

    sleep(5)

    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/filesystem/stat/'
    res = make_request('post', url, data=CLUSTER_PATH)
    assert res.status_code == 200, res.text
    data = res.json()
    mode = stat.S_IMODE(data['mode']) & ~stat.S_IFDIR
    assert data['acl'] is False
    assert f'{mode:03o}' == '777'

    payload = {'path': CLUSTER_PATH}
    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/filesystem/listdir/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    for entry in data:
        mode = stat.S_IMODE(entry['mode']) & ~stat.S_IFDIR
        assert entry['acl'] is False
        assert f'{mode:03o}' == '755' if stat.S_ISDIR(entry['mode']) else '644'


def test_010_filesystem_setperm_recursive(request):
    depends(request, ['FS_BASIC_TEST_FILES_CREATED'])
    payload = {
        "path": CLUSTER_PATH,
        "mode": "777",
        "options": {"recursive": True}
    }
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/filesystem/setperm/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text

    try:
        status = wait_on_job(res.json(), CLUSTER_IPS[0], FUSE_OP_TIMEOUT)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status

    payload = {'path': CLUSTER_PATH}
    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/filesystem/listdir/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    for entry in data:
        mode = stat.S_IMODE(entry['mode']) & ~stat.S_IFDIR
        assert entry['acl'] is False
        assert f'{mode:03o}' == '777'


def test_011_filesystem_reset_mode(request):
    depends(request, ['FS_BASIC_TEST_FILES_CREATED'])

    payload = {
        "path": CLUSTER_PATH,
        "mode": "755",
        "options": {"recursive": True}
    }
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/filesystem/setperm/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text

    try:
        status = wait_on_job(res.json(), CLUSTER_IPS[0], FUSE_OP_TIMEOUT)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status


def test_012_filesystem_setacl_nonrecursive(request):
    depends(request, ['FS_BASIC_TEST_FILES_CREATED'])

    payload = {"acl_type": "POSIX_RESTRICTED"}
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/filesystem/get_default_acl/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text

    to_set = res.json()

    payload = {
        "path": CLUSTER_PATH,
        "dacl": to_set,
        "acltype": "POSIX1E",
        "options": {"recursive": False}
    }

    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/filesystem/setacl/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text

    try:
        status = wait_on_job(res.json(), CLUSTER_IPS[0], FUSE_OP_TIMEOUT)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status

    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/filesystem/stat/'
    res = make_request('post', url, data=CLUSTER_PATH)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data['acl'] is True

    payload = {'path': CLUSTER_PATH}
    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/filesystem/listdir/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    for entry in data:
        assert entry['acl'] is False


def test_013_filesystem_setacl_recursive(request):
    depends(request, ['FS_BASIC_TEST_FILES_CREATED'])

    payload = {"acl_type": "POSIX_RESTRICTED"}
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/filesystem/get_default_acl/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text

    to_set = res.json()
    to_set.extend([
        {
            "default": True,
            "tag": "GROUP",
            "id": 1000,
            "perms": {"READ": True, "WRITE": True, "EXECUTE": True}
        },
        {
            "default": True,
            "tag": "MASK",
            "id": -1,
            "perms": {"READ": True, "WRITE": True, "EXECUTE": True}
        },
    ])

    payload = {
        "path": CLUSTER_PATH,
        "dacl": to_set,
        "acltype": "POSIX1E",
        "options": {"recursive": True}
    }

    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/filesystem/setacl/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text

    try:
        status = wait_on_job(res.json(), CLUSTER_IPS[0], FUSE_OP_TIMEOUT)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status

    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/filesystem/stat/'
    res = make_request('post', url, data=CLUSTER_PATH)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data['acl'] is True

    payload = {'path': CLUSTER_PATH}
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/filesystem/listdir/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    for entry in data:
        assert entry['acl'] is True


def test_014_filesystem_reset_acl(request):
    depends(request, ['FS_BASIC_TEST_FILES_CREATED'])

    payload = {
        "path": CLUSTER_PATH,
        "mode": "755",
        "options": {"recursive": True, "stripacl": True}
    }
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/filesystem/setperm/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text

    try:
        status = wait_on_job(res.json(), CLUSTER_IPS[0], FUSE_OP_TIMEOUT)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_015_filesystem_statfs(ip, request):
    depends(request, ['FS_BASIC_GLUSTER_VOLUME_MOUNTED'])

    url = f'http://{ip}/api/v2.0/filesystem/statfs/'
    res = make_request('post', url, data=CLUSTER_PATH)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data['fstype'] == 'fuse.glusterfs'
    assert data['source'] == f'localhost:/{CLUSTER_INFO["GLUSTER_VOLUME"]}'


def test_050_remove_test_files(request):
    depends(request, ['FS_BASIC_TEST_FILES_CREATED'])

    cmd = f'rm -rf {LOCAL_PATH}'
    res = ssh_test(CLUSTER_IPS[0], cmd)
    assert res['result'], res['stderr']
