import pytest

from config import CLUSTER_INFO, CLUSTER_IPS, TIMEOUTS
from exceptions import JobTimeOut
from pytest_dependency import depends
from time import sleep
from utils import make_request, make_ws_request, ssh_test, wait_on_job

def address_from_pnn(pnn):
    for address, data in ifaces_reclock_nodemap.items():
        if data['pnn'] == pnn:
            return address

    return None

@pytest.mark.dependency(name='INIT_NODEMAP_RECLOCK')
def test_001_get_nodemap(request):
    """
    Get our nodemap and store in global variable. We use this
    for keeping state between tests as we shift around IPs between nodes.
    """
    global ifaces_reclock_nodemap
    global recmaster
    ip = CLUSTER_IPS[0]
    payload = {
        'msg': 'method',
        'method': 'ctdb.general.listnodes',
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, res
    ifaces_reclock_nodemap = {x['address']: {'pnn': x['pnn']} for x in res['result']}

    payload = {
        'msg': 'method',
        'method': 'ctdb.general.recovery_master',
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, res

    recmaster = res['result']


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_002_reclock_helper(ip, request):
    """
    All nodes should report lock contention if try to trigger
    mutex helper script (even same node that currently holds it.

    Mutex helper prints `0` on stdout if successfully got
    mutex, `1` means mutex contention (expected value),
    and `3` means an error occurred.

    Error messages are printed to stderr.
    """
    depends(request, ['INIT_NODEMAP_RECLOCK'])
    res = ssh_test(ip, '/usr/local/sbin/ctdb_glfs_lock')
    assert res['result'] is True, str(res)
    assert res['output'] == '1', str(res)


def test_003_change_recovery_master(request):
    depends(request, ['INIT_NODEMAP_RECLOCK'])

    target = address_from_pnn(recmaster)
    assert target is not None, str({'recmaster': recmaster, 'nodemap': ifaces_reclock_nodemap})
    check_target = None
    slept = 0

    for ip in CLUSTER_IPS:
        if ip == target:
            continue

        check_target = ip
        break

    res = make_ws_request(target, {
        'msg': 'method',
        'method': 'service.stop',
        'params': ['ctdb']
    })
    assert res.get('error') is None, res

    ssh_test(target, 'python3 /usr/local/sbin/ctdb_reclock_helper --kill')
    assert res['result'], str(res)

    while slept < TIMEOUTS['LEADER_FAILOVER_TIMEOUT']:
        payload = {
            'msg': 'method',
            'method': 'ctdb.general.recovery_master',
        }

        res = make_ws_request(check_target, payload)
        assert res.get('error') is None, res
        if res['result'] != recmaster:
            break 

        sleep(1)
        slept += 1


    assert res['result'] != recmaster

    res = make_ws_request(target, {
        'msg': 'method',
        'method': 'service.start',
        'params': ['ctdb']
    })
    assert res.get('error') is None, res

    slept = 0
    while slept < TIMEOUTS['LEADER_FAILOVER_TIMEOUT']:
        payload = {
            'msg': 'method',
            'method': 'ctdb.general.healthy',
        }

        res = make_ws_request(check_target, payload)
        assert res.get('error') is None, res
        if res['result'] is True:
            break

    assert res['result'] == True
