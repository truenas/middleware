import pytest

from config import CLUSTER_INFO, CLUSTER_IPS, TIMEOUTS 
from utils import make_request, ssh_test, make_ws_request
from pytest_dependency import depends
from helpers import get_bool
from time import sleep


BOOL_SMB_PARAMS = {
    'ro': {'smbconf': 'read only', 'default': False},
    'browsable': {'smbconf': 'browseable', 'default': True},
    'abe': {'smbconf': 'access based share enum', 'default': False},
}

SHARE_FUSE_PATH = f'CLUSTER:{CLUSTER_INFO["GLUSTER_VOLUME"]}/smb_share_01'
SMB_SHARE_ID = None

def test_000_get_node_list(request):
    global smb_node_list
    payload = {
        'msg': 'method',
        'method': 'ctdb.general.listnodes',
    }
    res = make_ws_request(CLUSTER_IPS[0], payload)
    assert res.get('error') is None, res
    smb_node_list = res['result']


@pytest.mark.dependency(name="CLUSTER_INITIAL_CONFIG")
def test_001_check_initial_smb_config(request):
    payload = {
        'msg': 'method',
        'method': 'sharing.smb.reg_showshare',
        'params': ["GLOBAL"]
    }
    res = make_ws_request(CLUSTER_IPS[0], payload)
    assert res.get('error') is None, res
    data = res['result']['parameters']
    assert not data['server multi channel support']['parsed']
    assert not data['ntlm auth']['parsed']
    assert data['idmap config * : range']['raw'] == '90000001 - 100000000'
    assert data['server min protocol']['raw'] == 'SMB2_02'
    assert data['guest account']['raw'] == 'nobody'


@pytest.mark.dependency(name="CLUSTER_SMB_SHARE_CREATED")
def test_002_create_clustered_smb_share(request):
    depends(request, ['CLUSTER_INITIAL_CONFIG'])
    global SMB_SHARE_ID

    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/filesystem/mkdir/'
    res = make_request('post', url, data=SHARE_FUSE_PATH)
    assert res.status_code == 200, res.text

    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/sharing/smb/'
    payload = {
        "comment": "SMB VSS Testing Share",
        "path": '/smb_share_01',
        "name": "CL_SMB",
        "purpose": "NO_PRESET",
        "shadowcopy": False,
        "cluster_volname": CLUSTER_INFO["GLUSTER_VOLUME"]
    }

    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text
    SMB_SHARE_ID = res.json()['id']


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_003_verify_smb_share_exists(ip, request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    url = f'http://{ip}/api/v2.0/sharing/smb?id={SMB_SHARE_ID}'
    res = make_request('get', url)
    assert res.status_code == 200, res.text
    share = res.json()[0]
    assert share['cluster_volname'] == CLUSTER_INFO["GLUSTER_VOLUME"], str(share)
    assert share['name'] == 'CL_SMB', str(share)
    assert share['path_local'] == SHARE_FUSE_PATH, res.text


@pytest.mark.dependency(name="SMB_SERVICE_STARTED")
@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_004_start_smb_service(ip, request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])
    payload = {
        'msg': 'method',
        'method': 'service.start',
        'params': ['cifs', {'silent': False}]
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, res


def test_006_enable_recycle(request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    payload = {
        "recyclebin": True,
    }
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/sharing/smb/id/{SMB_SHARE_ID}'
    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_007_check_recycle_set(ip, request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    payload = {
        'msg': 'method',
        'method': 'sharing.smb.reg_showshare',
        'params': ["CL_SMB"]
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, res
    data = res['result']['parameters']
    assert 'recycle' in data['vfs objects']['parsed'], data
    assert data['recycle:keeptree']['parsed'], data
    assert data['recycle:versions']['parsed'], data
    assert data['recycle:touch']['parsed'], data
    assert data['recycle:directory_mode']['raw'] == '0777', data
    assert data['recycle:subdir_mode']['raw'] == '0700', data
    assert data['recycle:repository']['raw'] == '.recycle/%U', data


def test_008_disable_recycle(request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])
    payload = {
        "recyclebin": False,
    }
    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/sharing/smb/id/{SMB_SHARE_ID}'
    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_009_check_recycle_unset(ip, request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    payload = {
        'msg': 'method',
        'method': 'sharing.smb.reg_showshare',
        'params': ["CL_SMB"]
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, res

    data = res['result']['parameters']
    assert 'recycle' not in data['vfs objects']['parsed'], data
    assert data.get('recycle:keeptree') is None
    assert data.get('recycle:versions') is None
    assert data.get('recycle:touch') is None
    assert data.get('recycle:directory_mode') is None
    assert data.get('recycle:subdir_mode') is None
    assert data.get('recycle:repository') is None


def test_010_enable_smb_aapl(request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    payload = {
        "aapl_extensions": True,
    }
    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/smb/'
    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_011_check_aapl_extension_enabled(ip, request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    payload = {
        'msg': 'method',
        'method': 'sharing.smb.reg_showshare',
        'params': ["CL_SMB"]
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, res
    data = res['result']['parameters']
    assert 'fruit' in data['vfs objects']['parsed'], data
    assert 'streams_xattr' in data['vfs objects']['parsed'], data
    assert data['fruit:resource']['parsed'] == 'stream'
    assert data['fruit:metadata']['parsed'] == 'stream'


def test_014_enable_timemachine(request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    payload = {
        "timemachine": True,
    }
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/sharing/smb/id/{SMB_SHARE_ID}'
    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_015_check_timemachine_set(ip, request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    payload = {
        'msg': 'method',
        'method': 'sharing.smb.reg_showshare',
        'params': ["CL_SMB"]
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, res

    data = res['result']['parameters']
    assert 'fruit' in data['vfs objects']['parsed'], data
    assert data['fruit:time machine']['parsed']


def test_016_knownfail_disable_smb_aapl(request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    payload = {
        "aapl_extensions": False,
    }
    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/smb/'
    res = make_request('put', url, data=payload)
    assert res.status_code == 422, res.text


def test_017_disable_timemachine(request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    payload = {
        "timemachine": False,
    }
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/sharing/smb/id/{SMB_SHARE_ID}'
    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_018_check_timemachine_unset(ip, request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    payload = {
        'msg': 'method',
        'method': 'sharing.smb.reg_showshare',
        'params': ["CL_SMB"]
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, res

    data = res['result']['parameters']
    assert not data['fruit:time machine']['parsed']


def test_019_disable_smb_aapl(request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    payload = {
        "aapl_extensions": False,
    }
    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/smb/'
    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text


def test_020_disable_streams(request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    payload = {
        "streams": False,
    }
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/sharing/smb/id/{SMB_SHARE_ID}'
    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_021_check_streams_unset(ip, request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    payload = {
        'msg': 'method',
        'method': 'smb.getparm',
        'params': ["vfs objects", "CL_SMB"]
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, res
    assert 'streams_xattr' not in res['result']


def test_022_enable_streams(request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    payload = {
        "streams": True,
    }
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/sharing/smb/id/{SMB_SHARE_ID}'
    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_023_check_streams_set(ip, request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    payload = {
        'msg': 'method',
        'method': 'smb.getparm',
        'params': ["vfs objects", "CL_SMB"]
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, res
    assert 'streams_xattr' in res['result']


def test_024_share_comment(request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])
    payload = {"comment": "test comment"}
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/sharing/smb/id/{SMB_SHARE_ID}'
    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text

    for ip in CLUSTER_IPS:
        payload = {
            'msg': 'method',
            'method': 'smb.getparm',
            'params': ["comment", "CL_SMB"]
        }
        res = make_ws_request(ip, payload)
        assert res.get('error') is None, res
        assert res['result'] == 'test comment'

    payload = {"comment": ""}
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/sharing/smb/id/{SMB_SHARE_ID}'
    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text

    for ip in CLUSTER_IPS:
        payload = {
            'msg': 'method',
            'method': 'smb.getparm',
            'params': ["comment", "CL_SMB"]
        }
        res = make_ws_request(ip, payload)
        assert res.get('error') is None, res
        assert res['result'] == ''


@pytest.mark.parametrize('to_check', BOOL_SMB_PARAMS.keys())
def test_025_share_param_check_bool(to_check, request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    default_val = BOOL_SMB_PARAMS[to_check]['default']
    smbconf_param = BOOL_SMB_PARAMS[to_check]['smbconf']
    payload = {to_check: not default_val}
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/sharing/smb/id/{SMB_SHARE_ID}'

    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text

    for ip in CLUSTER_IPS:
        payload = {
            'msg': 'method',
            'method': 'smb.getparm',
            'params': [smbconf_param, "CL_SMB"]
        }
        res = make_ws_request(ip, payload)
        assert res.get('error') is None, res

        val = get_bool(res['result'])
        assert val is not default_val, f'IP: {ip}, param: {smbconf_param}, value: {res["result"]}'

    payload = {to_check: default_val}
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/sharing/smb/id/{SMB_SHARE_ID}'
    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text

    for ip in CLUSTER_IPS:
        payload = {
            'msg': 'method',
            'method': 'smb.getparm',
            'params': [smbconf_param, "CL_SMB"]
        }
        res = make_ws_request(ip, payload)
        assert res.get('error') is None, res

        val = get_bool(res['result'])
        assert val is default_val, f'IP: {ip}, param: {smbconf_param}, value: {res["result"]}'


@pytest.mark.parametrize('to_check', ['hostsallow', 'hostsdeny'])
def test_026_share_param_hosts(to_check, request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    rando_ips = ["192.168.0.240", "192.168.0.69"]
    payload = {to_check: rando_ips}
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/sharing/smb/id/{SMB_SHARE_ID}'
    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text

    for ip in CLUSTER_IPS:
        payload = {
            'msg': 'method',
            'method': 'smb.getparm',
            'params': [f'hosts {to_check[5:]}', "CL_SMB"]
        }
        res = make_ws_request(ip, payload)
        assert res.get('error') is None, res

        assert res['result'] == rando_ips

    payload = {to_check: []}
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/sharing/smb/id/{SMB_SHARE_ID}'
    res = make_request('put', url, data=payload)
    assert res.status_code == 200, res.text

    for ip in CLUSTER_IPS:
        payload = {
            'msg': 'method',
            'method': 'smb.getparm',
            'params': [f'hosts {to_check[5:]}', "CL_SMB"]
        }
        res = make_ws_request(ip, payload)
        assert res.get('error') is None, res

        assert res['result'] == []


@pytest.mark.parametrize('to_check', ['shadowcopy', 'fsrvp', 'afp', 'home'])
def test_027_knownfail_invalid_cluster_params(to_check, request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    payload = {to_check: True}
    url = f'http://{CLUSTER_IPS[0]}/api/v2.0/sharing/smb/id/{SMB_SHARE_ID}'
    res = make_request('put', url, data=payload)
    assert res.status_code == 422, res.text


def test_030_delete_smb_share(request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    url = f'http://{CLUSTER_IPS[1]}/api/v2.0/sharing/smb/id/{SMB_SHARE_ID}'
    res = make_request('delete', url)
    assert res.status_code == 200, res.text

    cmd = f'rm -rf /cluster/{CLUSTER_INFO["GLUSTER_VOLUME"]}/smb_share_01'
    res = ssh_test(CLUSTER_IPS[0], cmd)
    assert res['result'], res['output']


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_031_verify_share_removed(ip, request):
    depends(request, ['CLUSTER_SMB_SHARE_CREATED'])

    url = f'http://{ip}/api/v2.0/sharing/smb?id={SMB_SHARE_ID}'
    res = make_request('get', url)
    assert res.status_code == 200, res.text
    assert res.json() == [], res.text


@pytest.mark.dependency(name="SMB_SERVICE_STOPPED")
@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_032_disable_smb(ip, request):
    depends(request, ["SMB_SERVICE_STARTED"])

    url = f'http://{ip}/api/v2.0/service/stop'
    payload = {"service": "cifs"}

    res = make_request('post', url, data=payload)
    assert res.status_code == 200, res.text


def test_33_enable_service_monitor(request):
    def get_service_state():
        payload = {
            'msg': 'method',
            'method': 'ctdb.services.get',
        }
        res = make_ws_request(CLUSTER_IPS[0], payload)
        assert res.get('error') is None, res
        entry = [x for x in res['result'] if x['name'] == 'cifs']
        assert len(entry) == 1, str(res['result'])
        return entry[0]

    def check_monitored_state(expected):
        waited = 0
        while waited != TIMEOUTS['MONITOR_TIMEOUT']:
            entry = get_service_state()

            if any(x['state'] == 'UNAVAIL' for x in entry['cluster_state']):
                sleep(1)
                waited += 1
                continue

            states = {x['pnn']: x['state']['running'] for x in entry['cluster_state']}
            if states == expected:
                return entry

            sleep(1)
            waited += 1

        assert states == expected, str(entry)

    depends(request, ["SMB_SERVICE_STOPPED"])
    ip = CLUSTER_IPS[0]

    status = get_service_state()
    assert status['monitor_enable'] is False, str(entry)
    assert status['service_enable'] is False, str(entry)

    # enable monitoring. SMB should start on all nodes
    payload = {
        'msg': 'method',
        'method': 'ctdb.services.set',
        'params': ['cifs', {'monitor_enable': True, 'service_enable': True}],
    }
    res = make_ws_request(CLUSTER_IPS[0], payload)
    assert res.get('error') is None, res

    expected_state = {x['pnn']: True for x in smb_node_list}
    check_monitored_state(expected_state)

    payload = {
        'msg': 'method',
        'method': 'ctdb.services.set',
        'params': ['cifs', {'monitor_enable': True, 'service_enable': True}],
    }
    res = make_ws_request(CLUSTER_IPS[0], payload)
    assert res.get('error') is None, res

    expected_state = {x['pnn']: True for x in smb_node_list}
    check_monitored_state(expected_state)

    # Keep monitoring enabled, but disable service. SMB should stop on all nodes
    payload = {
        'msg': 'method',
        'method': 'ctdb.services.set',
        'params': ['cifs', {'monitor_enable': True, 'service_enable': False}],
    }
    res = make_ws_request(CLUSTER_IPS[0], payload)
    assert res.get('error') is None, res

    expected_state = {x['pnn']: False for x in smb_node_list}
    check_monitored_state(expected_state)

    # intentionally break SMB on node 0. Error should be reported.
    victim = [x['address'] for x in smb_node_list if x['pnn'] == 0]
    assert victim, str(smb_node_list)

    res = ssh_test(victim[0], 'chmod -x /usr/sbin/smbd')
    assert res['result'], res['output']

    payload = {
        'msg': 'method',
        'method': 'ctdb.services.set',
        'params': ['cifs', {'monitor_enable': True, 'service_enable': True}],
    }
    res = make_ws_request(CLUSTER_IPS[0], payload)
    assert res.get('error') is None, res

    expected_state = {x['pnn']: x['pnn'] != 0 for x in smb_node_list}
    service_state = check_monitored_state(expected_state)
    victim_state = [x for x in service_state['cluster_state'] if x['pnn'] == 0]
    assert victim_state[0]['state']['error'] is not None, str(service_state)

    res = ssh_test(victim[0], 'chmod +x /usr/sbin/smbd')
    assert res['result'], res['output']

    # Disable SMB again through monitor
    payload = {
        'msg': 'method',
        'method': 'ctdb.services.set',
        'params': ['cifs', {'monitor_enable': True, 'service_enable': False}],
    }
    res = make_ws_request(CLUSTER_IPS[0], payload)
    assert res.get('error') is None, res

    expected_state = {x['pnn']: False for x in smb_node_list}
    check_monitored_state(expected_state)

    # Disable monitor
    payload = {
        'msg': 'method',
        'method': 'ctdb.services.set',
        'params': ['cifs', {'monitor_enable': False, 'service_enable': False}],
    }
    res = make_ws_request(CLUSTER_IPS[0], payload)
    assert res.get('error') is None, res
