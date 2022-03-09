import pytest

from config import CLUSTER_INFO, CLUSTER_IPS
from utils import make_request, make_ws_request, wait_on_job
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


@pytest.mark.dependency(name='CREATE_GVOLUME')
def test_03_create_gluster_volume(request):
    depends(request, ['MOUNT_DATASETS'])
    payload = {
        'name': GVOL,
        'bricks': [{'peer_name': i, 'peer_path': BRICK_PATH} for i in CLUSTER_IPS],
        'force': True,
    }
    ans = make_request('post', '/gluster/volume', data=payload)
    assert ans.status_code == 200, ans.text

    # wait on the gluster volume to be created
    try:
        status = wait_on_job(ans.json(), CLUSTER_INFO['NODE_A_IP'], 120)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status

    # query a node for the volume
    payload = {'query-filters': [['name', '=', GVOL]]}
    ans = make_request('get', '/gluster/volume', data=payload)
    assert ans.status_code == 200, ans.text
    assert len(ans.json()) > 0 and any(i['id'] == GVOL for i in ans.json()), ans.text


@pytest.mark.dependency(name='START_GVOLUME')
def test_04_start_gluster_volume(request):
    depends(request, ['CREATE_GVOLUME'])
    ans = make_request('post', '/gluster/volume/start', data={'name': GVOL})
    assert ans.status_code == 200, ans.text


@pytest.mark.dependency(name='VERIFY_FUSE_MOUNTED')
def test_05_verify_gluster_volume_is_fuse_mounted(request):
    depends(request, ['START_GVOLUME'])
    result = {}
    # make sure all nodes have fuse mounted the gluster volume
    # (this should happen when the gluster volume is started)
    for ip in CLUSTER_IPS:
        url = f'http://{ip}/api/v2.0/gluster/fuse/is_mounted'
        ans = make_request('post', url, data={'name': GVOL})
        result.add((f'{ip} has fuse mount?', ans.json()))
    assert all(i[1] is True for i in result), result


@pytest.mark.dependency(name='STOP_GVOLUME')
def test_06_stop_gluster_volume(request):
    depends(request, ['START_GVOLUME'])
    ans = make_request('post', '/gluster/volume/stop', data={'name': GVOL, 'force': True})
    assert ans.status_code == 200, ans.text


@pytest.mark.dependency(name='VERIFY_FUSE_UMOUNTED')
def test_07_verify_gluster_volume_is_fuse_umounted(request):
    depends(request, ['VERIFY_FUSE_MOUNTED'])
    result = {}
    # make sure all nodes have fuse umounted the gluster volume
    # (this should happen when the gluster volume is stopped)
    for ip in CLUSTER_IPS:
        url = f'http://{ip}/api/v2.0/gluster/fuse/is_mounted'
        ans = make_request('post', url, data={'name': GVOL})
        result.add((f'{ip} has fuse mount?', ans.json()))
    assert all(i[1] is False for i in result), result


def test_08_delete_gluster_volume(request):
    depends(request, ['VERIFY_FUSE_UMOUNTED'])
    ans = make_request('delete', f'/gluster/volume/id/{GVOL}')
    assert ans.status_code == 200, ans.text

    ans = make_request('get', '/gluster/volume/list')
    assert ans.status_code == 200, ans.text
    assert GVOL not in ans.json(), ans.json()
