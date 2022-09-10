from time import sleep

import pytest

from config import CLUSTER_INFO, CLUSTER_IPS, TIMEOUTS
from utils import make_request, make_ws_request, wait_on_job, ssh_test
from exceptions import JobTimeOut
from pytest_dependency import depends


GVOL = 'gvolumetest'
DS_HIERARCHY = f'{CLUSTER_INFO["ZPOOL"]}/.glusterfs/{GVOL}/brick0'
BRICK_PATH = f'/mnt/{DS_HIERARCHY}'


@pytest.mark.parametrize('ip', CLUSTER_IPS)
@pytest.mark.dependency(name='CREATE_DS_HEIRARCHY')
def test_01_create_dataset_heirarchy(ip, request):
    # need to create the zfs dataset heirarchy
    payload = {
        'msg': 'method',
        'method': 'zfs.dataset.create',
        'params': [{
            'name': DS_HIERARCHY,
            'type': 'FILESYSTEM',
            'create_ancestors': True,
            'properties': {'acltype': 'posix'}
        }]
    }
    res = make_ws_request(ip, payload)
    assert not res.get('error', {}), res['error'].get('reason', 'NO REASON GIVEN')


@pytest.mark.parametrize('ip', CLUSTER_IPS)
@pytest.mark.dependency(name='MOUNT_DATASETS')
def test_02_mount_dataset_heirarchy(ip, request):
    depends(request, ['CREATE_DS_HEIRARCHY'])
    # libzfs doesnt mount the youngest ancestor when given
    # a path of ancestors during initial creation
    payload = {
        'msg': 'method',
        'method': 'zfs.dataset.mount',
        'params': [DS_HIERARCHY],
    }
    res = make_ws_request(ip, payload)
    assert not res.get('error', {}), res['error'].get('reason', 'NO REASON GIVEN')


@pytest.mark.parametrize('volume', [GVOL])
@pytest.mark.dependency(name='CREATE_GVOLUME')
def test_03_create_gluster_volume(volume, request):
    depends(request, ['MOUNT_DATASETS'])
    payload = {
        'name': volume,
        'bricks': [{'peer_name': i, 'peer_path': BRICK_PATH} for i in CLUSTER_IPS],
        'force': True,
    }
    ans = make_request('post', '/gluster/volume', data=payload)
    assert ans.status_code == 200, ans.text

    # wait on the gluster volume to be created
    try:
        status = wait_on_job(ans.json(), CLUSTER_INFO['NODE_A_IP'], TIMEOUTS['VOLUME_TIMEOUT'])
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status

    # query a node for the volume
    payload = {'query-filters': [['name', '=', volume]]}
    ans = make_request('get', '/gluster/volume', data=payload)
    assert ans.status_code == 200, ans.text
    res = ans.json()
    assert len(res) > 0 and res[0]['id'] == volume, ans.text


@pytest.mark.parametrize('volume', [GVOL])
@pytest.mark.dependency(name='STARTED_GVOLUME')
def test_04_verify_gluster_volume_is_started(volume, request):
    depends(request, ['CREATE_GVOLUME'])
    ans = make_request('post', '/gluster/volume/info', data={'name': volume})
    assert ans.status_code == 200, ans.text
    result = ans.json()
    assert len(result) > 0, f'Failed to retrieve gluster info for {volume}'
    assert result[0]['status'].lower() == 'started', result[0]


@pytest.mark.parametrize('ip', CLUSTER_IPS)
@pytest.mark.dependency(name='VERIFY_FUSE_MOUNTED')
def test_05_verify_gluster_volume_is_fuse_mounted(ip, request):
    depends(request, ['STARTED_GVOLUME'])

    total_time_to_wait = (TIMEOUTS['FUSE_OP_TIMEOUT'] * 2)
    sleepy_time = 1
    while total_time_to_wait > 0:
        # give each node a little time to actually fuse mount the volume before we claim failure
        ans = make_request('post', f'http://{ip}/api/v2.0/gluster/fuse/is_mounted', data={'name': GVOL})
        assert ans.status_code == 200

        if ans.json():
            break

        total_time_to_wait -= sleepy_time
        sleep(1)

    assert ans.json(), ans.text


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_06_verify_gluster_volume_fuse_cgroup(ip, request):
    # the fuse mounts locally should not be attached to the
    # parent middlewared process
    depends(request, ['VERIFY_FUSE_MOUNTED'])
    rv = ssh_test(ip, 'systemctl status middlewared')
    assert rv['output'], rv
    assert '/usr/sbin/glusterfs' not in rv['output'], rv


@pytest.mark.parametrize('volume', [GVOL])
@pytest.mark.dependency(name='STOP_GVOLUME')
def test_07_stop_gluster_volume(volume, request):
    depends(request, ['STARTED_GVOLUME'])
    ans = make_request('post', '/gluster/volume/stop', data={'name': volume, 'force': True})
    assert ans.status_code == 200, ans.text


@pytest.mark.parametrize('ip', CLUSTER_IPS)
@pytest.mark.dependency(name='VERIFY_FUSE_UMOUNTED')
def test_08_verify_gluster_volume_is_fuse_umounted(ip, request):
    depends(request, ['STOP_GVOLUME'])

    total_time_to_wait = 10
    sleepy_time = 1
    while total_time_to_wait > 0:
        # give each node a little time to actually umount the fuse volume before we claim failure
        ans = make_request('post', f'http://{ip}/api/v2.0/gluster/fuse/is_mounted', data={'name': GVOL})
        assert ans.status_code == 200
        if ans.json():
            total_time_to_wait -= sleepy_time
            sleep(1)
        break

    assert not ans.json(), ans.text


@pytest.mark.parametrize('volume', [GVOL])
def test_09_delete_gluster_volume(volume, request):
    depends(request, ['VERIFY_FUSE_UMOUNTED'])
    ans = make_request('delete', f'/gluster/volume/id/{volume}')
    assert ans.status_code == 200, ans.text
    try:
        # wait for it to be deleted
        wait_on_job(ans.json(), CLUSTER_INFO['NODE_A_IP'], TIMEOUTS['VOLUME_TIMEOUT'])
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        ans = make_request('get', '/gluster/volume/list')
        assert ans.status_code == 200, ans.text
        assert volume not in ans.json(), ans.text
