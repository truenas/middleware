import pytest
import string
import secrets

from config import CLUSTER_INFO, CLUSTER_IPS, TIMEOUTS
from exceptions import JobTimeOut
from helpers import smb_connection
from utils import make_request, ssh_test, make_ws_request, wait_on_job
from pytest_dependency import depends
from samba import ntstatus, NTSTATUSError


SHARE_FUSE_PATH = f'CLUSTER:{CLUSTER_INFO["GLUSTER_VOLUME"]}/smb_share_02'
alphabet = string.ascii_letters + string.digits
user_password = ''.join(secrets.choice(alphabet) for i in range(16))


@pytest.mark.dependency(name="CLUSTER_SMB_SHARE2_CREATED")
def test_001_create_clustered_smb_share2(request):
    global SMB_SHARE_ID

    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/filesystem/mkdir/'
    res = make_request('post', url, data=SHARE_FUSE_PATH)
    assert res.status_code == 200, res.text

    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/sharing/smb/'
    payload = {
        "comment": "CLUSTER_SMB_SHARE_2",
        "path": '/smb_share_02',
        "name": "CL_SMB2",
        "purpose": "NO_PRESET",
        "shadowcopy": False,
        "cluster_volname": CLUSTER_INFO["GLUSTER_VOLUME"]
    }

    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text
    SMB_SHARE_ID = res.json()['id']


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_002_verify_smb_share2_exists(ip, request):
    depends(request, ['CLUSTER_SMB_SHARE2_CREATED'])

    url = f'http://{ip}/api/v2.0/sharing/smb?id={SMB_SHARE_ID}'
    res = make_request('get', url)
    assert res.status_code == 200, res.text
    share = res.json()[0]
    assert share['cluster_volname'] == CLUSTER_INFO["GLUSTER_VOLUME"], str(share)
    assert share['name'] == 'CL_SMB2', str(share)
    assert share['path_local'] == SHARE_FUSE_PATH, res.text


@pytest.mark.dependency(name="SMB_SERVICE2_STARTED")
@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_004_start_smb_service(ip, request):
    depends(request, ['CLUSTER_SMB_SHARE2_CREATED'])
    payload = {
        'msg': 'method',
        'method': 'service.start',
        'params': ['cifs', {'silent': False}]
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, str(res['error'])


@pytest.mark.dependency(name="LOCAL_SMB_USERS_CREATED")
def test_005_create_users(request):
    depends(request, ["SMB_SERVICE2_STARTED"])

    res = make_ws_request(CLUSTER_IPS[0], {
        'msg': 'method',
        'method': 'cluster.accounts.group.create',
        'params': [{'group': 'clustered_users'}]
    })
    assert res.get('error') is None, res
    common_gid = res['result']['gid']
    uids = []

    for i in range(0, 5):
        res = make_ws_request(CLUSTER_IPS[0], {
            'msg': 'method',
            'method': 'cluster.accounts.user.create',
            'params': [{
                'username': f'clustered_user_{i}',
                'full_name': f'clustered_user_{i}',
                'password': user_password,
            }]
        })
        assert res.get('error') is None, str(res['error'])
        uids.append(res['result']['uid'])

    res = make_ws_request(CLUSTER_IPS[0], {
        'msg': 'method',
        'method': 'cluster.accounts.group.update',
        'params': [common_gid, {'users': uids}]
    })
    assert res.get('error') is None, res

    # Make sure new group can write to share path
    res = make_ws_request(CLUSTER_IPS[0], {
        'msg': 'method',
        'method': 'filesystem.add_to_acl',
        'params': [{
            'path': SHARE_FUSE_PATH,
            'entries': [{'id_type': 'GROUP', 'id': common_gid, 'access': 'MODIFY'}]
        }]
    })
    assert res.get('error') is None, str(res['error'])

    try:
        status = wait_on_job(res['result'], CLUSTER_IPS[0], TIMEOUTS['FUSE_OP_TIMEOUT'])
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status


@pytest.mark.dependency(name="LOCAL_SMB_USERS_VALIDATED")
@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_006_validate_users(ip, request):
    depends(request, ['LOCAL_SMB_USERS_CREATED'])

    payload = {'groupname': 'clustered_users'}
    url = f'http://{ip}/api/v2.0/group/get_group_obj/'
    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text

    assert len(res.json()['gr_mem']) == 5, res.text

    for i in range(0, 5):
        payload = {'username': f'clustered_user_{i}'}
        url = f'http://{ip}/api/v2.0/user/get_user_obj/'
        res = make_request('post', url, data=payload)
        assert res.status_code == 200, res.text


@pytest.mark.dependency(name="LOCAL_SMB_SHARE_ACCESS")
@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_007_test_share_access(ip, request):
    depends(request, ['LOCAL_SMB_USERS_VALIDATED'])

    with smb_connection(
        host=ip,
        share='CL_SMB2',
        username='clustered_user_1',
        password=user_password,
        smb1=False
    ) as tcon:
        fd = tcon.create_file(f'testfile_{ip}', 'w')
        tcon.close(fd, True)


@pytest.mark.dependency(name="LOCAL_SMB_USER_DISABLED")
def test_008_lock_smb_user(request):
    depends(request, ['LOCAL_SMB_SHARE_ACCESS'])

    res = make_ws_request(CLUSTER_IPS[0], {
        'msg': 'method',
        'method': 'cluster.accounts.user.query',
        'params': [[['username', '=', 'clustered_user_1']], {'get': True}]
    })
    assert res.get('error') is None, res

    res = make_ws_request(CLUSTER_IPS[0], {
        'msg': 'method',
        'method': 'cluster.accounts.user.update',
        'params': [res['result']['uid'], {'locked': True}]
    })
    assert res.get('error') is None, str(res['error'])
    assert res['result']['locked'] is True, str(res['result'])


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_009_locked_smb_user_access_denied(ip, request):
    depends(request, ['LOCAL_SMB_USER_DISABLED'])

    with pytest.raises(NTSTATUSError) as e:
        with smb_connection(
            host=ip,
            share='CL_SMB2',
            username='clustered_user_1',
            password=user_password,
            smb1=False
        ) as tcon:
            fd = tcon.create_file(f'testfile_{ip}', 'w')
            tcon.close(fd, True)
            assert fd is not None, 'Access to share was possible while user locked'

        assert e.value.args[0] == ntstatus.NT_STATUS_ACCESS_DENIED, str(e)


def test_010_test_local_user_collision(request):
    depends(request, ['LOCAL_SMB_USERS_VALIDATED'])

    res = make_ws_request(CLUSTER_IPS[1], {
        'msg': 'method',
        'method': 'user.create',
        'params': [{
            'username': 'local_smb_user',
            'full_name': 'local_smb_user',
            'group_create': True,
            'password': user_password,
            'smb': True
        }]
    })
    # First attempt should fail because we're trying to create an SMB user
    # which is disallowed on cluster
    assert res.get('error') is not None, str(res['result'])
    assert res['error']['type'] == 'VALIDATION', str(res['error'])

    res = make_ws_request(CLUSTER_IPS[1], {
        'msg': 'method',
        'method': 'user.create',
        'params': [{
            'username': 'local_smb_user',
            'full_name': 'local_smb_user',
            'group_create': True,
            'password': user_password,
            'smb': False
        }]
    })
    assert res.get('error') is None, str(res['error'])

    # This request should fail since name collides with local user
    # on other node
    res = make_ws_request(CLUSTER_IPS[0], {
        'msg': 'method',
        'method': 'cluster.accounts.user.create',
        'params': [{
            'username': 'local_smb_user',
            'full_name': 'local_smb_user',
            'password': user_password,
        }]
    })
    assert res.get('error') is not None, str(res['result'])
    assert res['error']['type'] == 'VALIDATION', str(res['error'])


def test_029_delete_local_users_and_group(request):
    depends(request, ['LOCAL_SMB_USERS_CREATED'])

    res = make_ws_request(CLUSTER_IPS[0], {
        'msg': 'method',
        'method': 'cluster.accounts.user.query',
        'params': []
    })
    assert res.get('error') is None, str(res['error'])

    users = res['result']

    # Delete all users
    for u in users:
        res = make_ws_request(CLUSTER_IPS[0], {
            'msg': 'method',
            'method': 'cluster.accounts.user.delete',
            'params': [u['uid']]
        })
        assert res.get('error') is None, str(res['error'])

    res = make_ws_request(CLUSTER_IPS[0], {
        'msg': 'method',
        'method': 'cluster.accounts.group.query',
        'params': []
    })
    assert res.get('error') is None, str(res['error'])

    groups = res['result']
    # We should only have one group left (primary groups of users should be deleted)
    assert len(groups) == 1, str(groups)
    assert groups[0]['group'] == 'clustered_users', str(groups[0])

    res = make_ws_request(CLUSTER_IPS[0], {
        'msg': 'method',
        'method': 'cluster.accounts.group.delete',
        'params': [groups[0]['gid']]
    })
    assert res.get('error') is None, str(res['error'])

    # Verify that all users deleted
    res = make_ws_request(CLUSTER_IPS[0], {
        'msg': 'method',
        'method': 'cluster.accounts.user.query',
        'params': []
    })
    assert res.get('error') is None, str(res['error'])
    assert len(res['result']) == 0, str(res['result'])

    # Verify all groups deleted
    res = make_ws_request(CLUSTER_IPS[0], {
        'msg': 'method',
        'method': 'cluster.accounts.group.query',
        'params': []
    })
    assert res.get('error') is None, str(res['error'])
    assert len(res['result']) == 0, str(res['result'])


def test_030_delete_smb_share(request):
    depends(request, ['CLUSTER_SMB_SHARE2_CREATED'])

    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/sharing/smb/id/{SMB_SHARE_ID}'
    res = make_request('delete', url)
    assert res.status_code == 200, res.text

    cmd = f'rm -rf /cluster/{CLUSTER_INFO["GLUSTER_VOLUME"]}/smb_share_01'
    res = ssh_test(CLUSTER_IPS[0], cmd)
    assert res['result'], res['output']


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_031_verify_share2_removed(ip, request):
    depends(request, ['CLUSTER_SMB_SHARE2_CREATED'])

    url = f'http://{ip}/api/v2.0/sharing/smb?id={SMB_SHARE_ID}'
    res = make_request('get', url)
    assert res.status_code == 200, res.text
    assert res.json() == [], res.text


@pytest.mark.dependency(name="SMB_SERVICE_STOPPED")
@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_032_disable_smb(ip, request):
    depends(request, ["SMB_SERVICE2_STARTED"])

    url = f'http://{ip}/api/v2.0/service/stop'
    payload = {"service": "cifs"}

    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text
