from time import sleep

import contextlib
import pytest

from config import CLUSTER_INFO, CLUSTER_IPS, TIMEOUTS, BRICK_PATH
from utils import make_request, make_ws_request, wait_on_job, ssh_test
from exceptions import JobTimeOut
from pytest_dependency import depends


GVOL = 'gvolumetest'
DS_PREFIX = f'{CLUSTER_INFO["ZPOOL"]}/.glusterfs'
DS_HIERARCHY = f'{DS_PREFIX}/{GVOL}/brick0'
BRICK_PATH2 = f'/mnt/{DS_HIERARCHY}'

REPLICATE = {
    'volume_name': 'test_rep',
    'local_node_configuration': {
        'hostname': CLUSTER_INFO['NODE_A_DNS'],
        'brick_path': f'/mnt/{DS_PREFIX}/test_rep/brick0'
    },
    'peers': [
        {'peer_name': CLUSTER_INFO['NODE_B_DNS'], 'peer_path': f'/mnt/{DS_PREFIX}/test_rep/brick0'},
        {'peer_name': CLUSTER_INFO['NODE_C_DNS'], 'peer_path': f'/mnt/{DS_PREFIX}/test_rep/brick0'},
    ],
    'volume_configuration': {'brick_layout': {'replica': 3, 'replica_distribute': 1}},
    'node_brick_cnt': 1
}
DISTRIBUTED_REPLICATE = {
    'volume_name': 'test_drep',
    'local_node_configuration': {
        'hostname': CLUSTER_INFO['NODE_A_DNS'],
        'brick_path': f'/mnt/{DS_PREFIX}/test_drep/brick0'
    },
    'peers': [
        {'peer_name': CLUSTER_INFO['NODE_B_DNS'], 'peer_path': f'/mnt/{DS_PREFIX}/test_drep/brick0'},
        {'peer_name': CLUSTER_INFO['NODE_C_DNS'], 'peer_path': f'/mnt/{DS_PREFIX}/test_drep/brick0'},
        {'peer_name': CLUSTER_INFO['NODE_A_DNS'], 'peer_path': f'/mnt/{DS_PREFIX}/test_drep/brick1'},
        {'peer_name': CLUSTER_INFO['NODE_B_DNS'], 'peer_path': f'/mnt/{DS_PREFIX}/test_drep/brick1'},
        {'peer_name': CLUSTER_INFO['NODE_C_DNS'], 'peer_path': f'/mnt/{DS_PREFIX}/test_drep/brick1'},
    ],
    'volume_configuration': {'brick_layout': {'replica': 3, 'replica_distribute': 2}},
    'node_brick_cnt': 2
}

DISPERSED = {
    'volume_name': 'test_disp',
    'local_node_configuration': {
        'hostname': CLUSTER_INFO['NODE_A_DNS'],
        'brick_path': f'/mnt/{DS_PREFIX}/test_disp/brick0'
    },
    'peers': [
        {'peer_name': CLUSTER_INFO['NODE_B_DNS'], 'peer_path': f'/mnt/{DS_PREFIX}/test_disp/brick0'},
        {'peer_name': CLUSTER_INFO['NODE_C_DNS'], 'peer_path': f'/mnt/{DS_PREFIX}/test_disp/brick0'},
    ],
    'volume_configuration': {'brick_layout': {
        'disperse_data': 2, 'disperse_redundancy': 1, 'disperse_distribute': 1,
    }},
    'node_brick_cnt': 1
}

DISTRIBUTED_DISPERSED = {
    'volume_name': 'test_ddisp',
    'local_node_configuration': {
        'hostname': CLUSTER_INFO['NODE_A_DNS'],
        'brick_path': f'/mnt/{DS_PREFIX}/test_ddisp/brick0'
    },
    'peers': [
        {'peer_name': CLUSTER_INFO['NODE_B_DNS'], 'peer_path': f'/mnt/{DS_PREFIX}/test_ddisp/brick0'},
        {'peer_name': CLUSTER_INFO['NODE_C_DNS'], 'peer_path': f'/mnt/{DS_PREFIX}/test_ddisp/brick0'},
        {'peer_name': CLUSTER_INFO['NODE_A_DNS'], 'peer_path': f'/mnt/{DS_PREFIX}/test_ddisp/brick1'},
        {'peer_name': CLUSTER_INFO['NODE_B_DNS'], 'peer_path': f'/mnt/{DS_PREFIX}/test_ddisp/brick1'},
        {'peer_name': CLUSTER_INFO['NODE_C_DNS'], 'peer_path': f'/mnt/{DS_PREFIX}/test_ddisp/brick1'},
    ],
    'volume_configuration': {'brick_layout': {
        'disperse_data': 2, 'disperse_redundancy': 1, 'disperse_distribute': 2
    }},
    'node_brick_cnt': 2
}


def setup_dataset_heirarchy(ip, volume_name, brick):
    datasets = f'{CLUSTER_INFO["ZPOOL"]}/.glusterfs/{volume_name}/{brick}'
    payload = {
        'msg': 'method',
        'method': 'zfs.dataset.create',
        'params': [{
            'name': datasets,
            'type': 'FILESYSTEM',
            'create_ancestors': True,
            'properties': {'acltype': 'posix'}
        }]
    }
    res = make_ws_request(ip, payload)
    assert not res.get('error', {}), res['error'].get('reason', 'NO REASON GIVEN')

    payload = {
        'msg': 'method',
        'method': 'zfs.dataset.mount',
        'params': [datasets],
    }
    res = make_ws_request(ip, payload)
    assert not res.get('error', {}), res['error'].get('reason', 'NO REASON GIVEN')


def remove_gluster_volume(volume_name):
    res = make_ws_request(CLUSTER_IPS[0], {
        'msg': 'method',
        'method': 'gluster.volume.stop',
        'params': [{'name': volume_name}]
    })

    assert not res.get('error', {}), res['error'].get('reason', 'NO REASON GIVEN')

    res = make_ws_request(CLUSTER_IPS[0], {
        'msg': 'method',
        'method': 'gluster.volume.delete',
        'params': [volume_name]
    })

    assert not res.get('error', {}), res['error'].get('reason', 'NO REASON GIVEN')

    try:
        # wait for it to be deleted
        wait_on_job(res['result'], CLUSTER_IPS[0], TIMEOUTS['VOLUME_TIMEOUT'])
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        ans = make_request('get', '/gluster/volume/list')
        assert ans.status_code == 200, ans.text
        assert volume_name not in ans.json(), ans.text


@contextlib.contextmanager
def create_gluster_volume(payload):
    """
    payload will have following keys:
    `volume_name` - name of gluster volume to be created
    `volume_configuration.brick_layout` - details of volume brick layout
    `local_node_configuration.hostname` - hostname of node0
    `local_node_configuration.brick_path` - some brick path on node0 to use
    `peers` - list of dicts with following keys:
    `peer_name` - hostname of peer
    `peer_path` - brick path on peer

    yields volume info of new gluster volume
    """
    for ip in CLUSTER_IPS:
        for i in range(0, payload['node_brick_cnt']):
            setup_dataset_heirarchy(ip, payload['volume_name'], f'brick{i}')

    res = make_ws_request(CLUSTER_IPS[0], {
        'msg': 'method',
        'method': 'cluster.management.validate_brick_layout',
        'params': [
            f'payload_validate_{payload["volume_name"]}',
            payload
        ]
    })
    assert not res.get('error', {}), res['error'].get('reason', 'NO REASON GIVEN')
    layout = res['result']

    create_payload = {'name': payload['volume_name'], 'force': True} | layout['layout']
    create_payload['bricks'] = [{
        'peer_name': payload['local_node_configuration']['hostname'],
        'peer_path': payload['local_node_configuration']['brick_path']
    }]

    create_payload['bricks'].extend(payload['peers'])

    res = make_ws_request(CLUSTER_IPS[0], {
        'msg': 'method',
        'method': 'gluster.volume.create',
        'params': [create_payload]
    })
    assert not res.get('error', {}), res['error'].get('reason', 'NO REASON GIVEN')

    try:
        # wait for it to be deleted
        res = wait_on_job(res['result'], CLUSTER_IPS[0], TIMEOUTS['VOLUME_TIMEOUT'])
    except JobTimeOut:
        assert False, JobTimeOut

    try:
        yield res['result']['result'][0]
    finally:
        remove_gluster_volume(payload['volume_name'])


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
        'bricks': [{'peer_name': i, 'peer_path': BRICK_PATH2} for i in CLUSTER_IPS],
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


@pytest.mark.parametrize('volume_info', [
    ('REPLICATE', REPLICATE),
    ('DISTRIBUTED_REPLICATE', DISTRIBUTED_REPLICATE),
    ('DISPERSE', DISPERSED),
    ('DISTRIBUTED_DISPERSE', DISTRIBUTED_DISPERSED),
])
def test_10_create_volume_types(volume_info, request):
    volume_type, payload = volume_info
    with create_gluster_volume(payload) as vol:
        assert vol['type'] == volume_type


@pytest.mark.dependency(name='CLUSTER_EXPANDED')
def test_11_expand_cluster(request):
    peers_config = [{
        'private_address': CLUSTER_INFO['NODE_D_IP'],
        'hostname': CLUSTER_INFO['NODE_D_DNS'],
        'brick_path': BRICK_PATH,
        'remote_credential': {
            'username': CLUSTER_INFO['APIUSER'],
            'password': CLUSTER_INFO['APIPASS']
        },
    }]

    payload = {
        'msg': 'method',
        'method': 'cluster.management.add_nodes',
        'params': [{
            'new_cluster_nodes': peers_config,
            'options': {'rebalance_volume': True}
        }]
    }
    res = make_ws_request(CLUSTER_INFO['NODE_A_IP'], payload)
    assert res.get('error') is None, str(res)

    try:
        status = wait_on_job(res['result'], CLUSTER_INFO['NODE_A_IP'], TIMEOUTS['VOLUME_TIMEOUT'])
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', str(status)

    gluster_volume = status['result']['result']['gluster_volume'][0]
    gluster_peers = status['result']['result']['gluster_peers']
    ctdb_config = status['result']['result']['ctdb_configuration']

    assert gluster_volume.get('name') == CLUSTER_INFO['GLUSTER_VOLUME'], str(gluster_volume)
    assert len(gluster_volume.get('bricks', [])) == 4, str(gluster_volume)
    assert len(gluster_peers) == 4, str(gluster_peers)
    assert len(ctdb_config['private_ips']) == 4, str(ctdb_config['private_ips'])

    res = make_ws_request(CLUSTER_INFO['NODE_D_IP'], {
        'msg': 'method',
        'method': 'ctdb.general.status',
        'params': []
    })

    assert res.get('error') is None, str(res)
    assert res['result']['all_healthy'] is True, str(res['result'])
