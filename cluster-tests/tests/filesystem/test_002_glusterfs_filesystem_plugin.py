import pytest
import stat

from config import CLUSTER_INFO, CLUSTER_IPS, TIMEOUTS
from contextlib import contextmanager
from copy import deepcopy
from exceptions import JobTimeOut
from utils import make_ws_request, wait_on_job
from pytest_dependency import depends

FUSE_OP_TIMEOUT = TIMEOUTS['FUSE_OP_TIMEOUT']

BINARY_DATA_SAMPLE = "YnBsaXN0MDCgCAAAAAAAAAEBAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAJ"
STRING_DATA_SAMPLE = 'FLUFFY_BUNNIES'


@contextmanager
def create_test_object(ip, is_dir, **kwargs):
    method = 'gluster.filesystem.mkdir'

    if not is_dir:
        method = 'gluster.filesystem.create_file'

    params = deepcopy(kwargs)

    payload = {
        'msg': 'method',
        'method': method,
        'params': [params]
    }

    unlink_params = {
        'volume_name': params['volume_name'],
        'parent_uuid': params.get('parent_uuid'),
        'path': params['path'],
        'gluster-volume-options': params.get('gluster-volume-options')
    }

    res = make_ws_request(ip, payload)
    assert res.get('error') is None, res

    try:
        yield res['result']
    finally:
        res = make_ws_request(ip, {
            'msg': 'method',
            'method': 'gluster.filesystem.unlink',
            'params': [unlink_params]
        })


@pytest.mark.dependency(name="HAS_ROOT_UUID")
def test_000_get_root_handle(request):
    global root_uuid
    ip = CLUSTER_IPS[0]

    payload = {
        'msg': 'method',
        'method': 'gluster.filesystem.lookup',
        'params': [{
            'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
            'path': '/',
        }]
    }

    res = make_ws_request(ip, payload)

    assert res.get('error') is None, res
    root_uuid = res['result']['uuid']


def test_001_create_unlink_file(request):
    depends(request, ['HAS_ROOT_UUID'])
    ip = CLUSTER_IPS[0]

    with create_test_object(ip, False, **{
        'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
        'path': 'GFAPI_TESTFILE1',
    }) as gl_obj:
        assert gl_obj['file_type']['parsed'] == 'FILE'
        res = make_ws_request(ip, {
            'msg': 'method',
            'method': 'gluster.filesystem.contents',
            'params': [{
                'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
                'uuid': root_uuid
            }]
        })

        assert res.get('error') is None, res
        assert 'GFAPI_TESTFILE1' in res['result']


def test_002_create_unlink_dir(request):
    depends(request, ['HAS_ROOT_UUID'])
    ip = CLUSTER_IPS[0]

    with create_test_object(ip, True, **{
        'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
        'path': 'GFAPI_TESTDIR1',
    }) as gl_obj:
        assert gl_obj['file_type']['parsed'] == 'DIRECTORY'

        res = make_ws_request(ip, {
            'msg': 'method',
            'method': 'gluster.filesystem.contents',
            'params': [{
                'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
                'uuid': root_uuid
            }]
        })

        assert res.get('error') is None, res
        assert 'GFAPI_TESTDIR1' in res['result']


def test_003_read_write_file(request):
    depends(request, ['HAS_ROOT_UUID'])
    STRING_DATA_SAMPLE = 'FLUFFY_BUNNIES'
    ip = CLUSTER_IPS[0]

    with create_test_object(ip, False, **{
        'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
        'path': 'GFAPI_TESTFILE_RW',
    }) as gl_obj:
        assert gl_obj['file_type']['parsed'] == 'FILE'

        # First start with writing / reading via string
        res = make_ws_request(ip, {
            'msg': 'method',
            'method': 'gluster.filesystem.pwrite',
            'params': [{
                'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
                'uuid': gl_obj['uuid'],
                'payload': STRING_DATA_SAMPLE
            }]
        })

        assert res.get('error') is None, res

        res = make_ws_request(ip, {
            'msg': 'method',
            'method': 'gluster.filesystem.contents',
            'params': [{
                'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
                'uuid': gl_obj['uuid']
            }]
        })

        assert res.get('error') is None, res
        assert res['result'] == STRING_DATA_SAMPLE

        # Now write binary content
        # new pwrite() request starts at offset 0 and so
        # this will overwrite the previous contents
        res = make_ws_request(ip, {
            'msg': 'method',
            'method': 'gluster.filesystem.pwrite',
            'params': [{
                'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
                'uuid': gl_obj['uuid'],
                'payload': BINARY_DATA_SAMPLE,
                'payload_type': 'BINARY'
            }]
        })
        assert res.get('error') is None, res

        res = make_ws_request(ip, {
            'msg': 'method',
            'method': 'gluster.filesystem.pread',
            'params': [{
                'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
                'uuid': gl_obj['uuid'],
                'options': {'offset': 0, 'cnt': len(BINARY_DATA_SAMPLE)}
            }]
        })
        assert res.get('error') is None, res
        assert res['result'] == BINARY_DATA_SAMPLE

        res = make_ws_request(ip, {
            'msg': 'method',
            'method': 'gluster.filesystem.contents',
            'params': [{
                'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
                'uuid': gl_obj['uuid'],
                'options': {'file_output_type': 'BINARY'}
            }]
        })
        assert res.get('error') is None, res
        assert res['result'] == BINARY_DATA_SAMPLE


def test_004_setattrs(request):
    depends(request, ['HAS_ROOT_UUID'])
    ip = CLUSTER_IPS[0]


    with create_test_object(ip, True, **{
        'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
        'path': 'GFAPI_TESTDIR_SETATTRS',
    }) as gl_obj:
        # create a bunch of test files
        for i in range(0, 100):
            res = make_ws_request(ip, {
                'msg': 'method',
                'method': 'gluster.filesystem.create_file',
                'params': [{
                    'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
                    'parent_uuid': gl_obj['uuid'],
                    'path': f'TMPFILE_{i}'
                }]
            })
            assert res.get('error') is None, res

        res = make_ws_request(ip, {
            'msg': 'method',
            'method': 'gluster.filesystem.contents',
            'params': [{
                'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
                'uuid': gl_obj['uuid'],
            }]
        })
        assert res.get('error') is None, res
        assert len(res['result']) == 100

        res = make_ws_request(ip, {
            'msg': 'method',
            'method': 'gluster.filesystem.setattrs',
            'params': [{
                'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
                'uuid': gl_obj['uuid'],
                'options': {
                    'uid': 1005,
                    'gid': 1010,
                    'mode': 0o700,
                    'recursive': True
                },
            }]
        })
        assert res.get('error') is None, res
        try:
            status = wait_on_job(res['result'], ip, 300)
        except JobTimeOut:
            assert False, JobTimeOut
        else:
            assert status['state'] == 'SUCCESS', status

        for i in range(0, 100):
            res = make_ws_request(ip, {
                'msg': 'method',
                'method': 'gluster.filesystem.lookup',
                'params': [{
                    'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
                    'parent_uuid': gl_obj['uuid'],
                    'path': f'TMPFILE_{i}'
                }]
            })
            assert res.get('error') is None, res
            assert res['result']['file_type']['parsed'] == 'FILE'
            assert res['result']['stat']['st_uid'] == 1005
            assert res['result']['stat']['st_gid'] == 1010

            mode = stat.S_IMODE(res['result']['stat']['st_mode']) & ~stat.S_IFDIR
            assert mode == 0o700

            res = make_ws_request(ip, {
                'msg': 'method',
                'method': 'gluster.filesystem.unlink',
                'params': [{
                    'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
                    'parent_uuid': gl_obj['uuid'],
                    'path': f'TMPFILE_{i}'
                }]
            })
            assert res.get('error') is None, res


def test_005_rmtree(request):
    depends(request, ['HAS_ROOT_UUID'])
    ip = CLUSTER_IPS[0]

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'gluster.filesystem.mkdir',
        'params': [{
            'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
            'parent_uuid': None,
            'path': 'to_delete'
        }]
    })

    assert res.get('error') is None, res
    root = res['result']

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'gluster.filesystem.create_file',
        'params': [{
            'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
            'parent_uuid': root['uuid'],
            'path': 'testfile1'
        }]
    })

    assert res.get('error') is None, res

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'gluster.filesystem.mkdir',
        'params': [{
            'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
            'parent_uuid': root['uuid'],
            'path': 'subdir'
        }]
    })

    assert res.get('error') is None, res
    subdir = res['result']

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'gluster.filesystem.create_file',
        'params': [{
            'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
            'parent_uuid': subdir['uuid'],
            'path': 'testfile2'
        }]
    })

    assert res.get('error') is None, res


    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'gluster.filesystem.rmtree',
        'params': [{
            'volume_name': CLUSTER_INFO['GLUSTER_VOLUME'],
            'parent_uuid': None,
            'path': 'to_delete'
        }]
    })

    assert res.get('error') is None, res

    try:
        status = wait_on_job(res['result'], ip, 300)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status
