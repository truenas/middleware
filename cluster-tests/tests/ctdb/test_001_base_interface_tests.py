import pytest

from config import CLUSTER_INFO, CLUSTER_IPS, PUBLIC_IPS
from exceptions import JobTimeOut
from pytest_dependency import depends
from utils import make_request, make_ws_request, wait_on_job


def update_active_ifaces(pnn, data):
    """
    Update interface information in our global dict.
    This dict is indexed by private IP address and
    {<private_ip>: {'pnn': <int>, 'active_interfaces': [<public address>]}}
    """
    reverse_lookup = {value['pnn']: key for key, value in ifaces_nodemap.items()}
    assert pnn in reverse_lookup

    ifaces_nodemap[reverse_lookup[pnn]].update({
        'active_interfaces': data['active_ips'].keys()
    })


def node_by_public_address(addr):
    """
    return tuple of private ip and ifaces_nodemap dict value.
    See above comment for further details about contents.
    """
    res = None

    for private_ip, data in ifaces_nodemap.items():
        if addr not in data['active_interfaces']:
            continue

        res = (private_ip, data)

    assert res is not None, f'request: {addr}, nodemap: {ifaces_nodemap}'

    return res


@pytest.mark.dependency(name='INIT_NODEMAP_GLOBAL')
def test_001_get_nodmap(request):
    """
    Get our nodemap and store in global variable. We use this
    for keeping state between tests as we shift around IPs between nodes.
    """
    global ifaces_nodemap
    ip = CLUSTER_IPS[0]
    payload = {
        'msg': 'method',
        'method': 'ctdb.general.listnodes',
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, res
    ifaces_nodemap = {x['address']: {'pnn': x['pnn']} for x in res['result']}


@pytest.mark.dependency(name='INTERFACES_CONFIGURED')
@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_002_validate_configured_interfaces(ip, request):
    """
    This validates that interfaces are configured on all nodes and
    also initializes the "active_interfaces" for each node in the
    global ifaces_nodemap that will be used in subsequent tests.
    """
    depends(request, ['INIT_NODEMAP_GLOBAL'])
    payload = {
        'msg': 'method',
        'method': 'ctdb.public.ips.query',
        'params': [[['pnn', '=', ifaces_nodemap[ip]['pnn']]], {'get': True}]
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, f'global_nodemap: {ifaces_nodemap}, ip: {ip}, {res}'

    configured_ips = set(res['result']['configured_ips'].keys())
    public_ips = set(PUBLIC_IPS)
    assert configured_ips == public_ips
    update_active_ifaces(res['result']['pnn'], res['result'])


@pytest.mark.dependency(name='INTERFACE_REMOVED')
def test_003_remove_public_ip(request):
    """
    This test removes a public IP from server by following
    it from node to node.
    """
    depends(request, ['INTERFACES_CONFIGURED'])
    to_remove = PUBLIC_IPS[0]

    for i in range(len(CLUSTER_IPS)):
        target = node_by_public_address(to_remove)
        payload = {
            'msg': 'method',
            'method': 'ctdb.public.ips.delete',
            'params': [to_remove]
        }
        res = make_ws_request(target[0], payload)
        assert res.get('error') is None, res

        try:
            status = wait_on_job(res['result'], target[0], 10)
        except JobTimeOut:
            assert False, JobTimeOut
        else:
            assert status['state'] == 'SUCCESS', status

        payload = {
            'msg': 'method',
            'method': 'ctdb.public.ips.query',
        }
        res = make_ws_request(target[0], payload)
        assert res.get('error') is None, res

        for entry in res['result']:
            update_active_ifaces(entry['pnn'], entry)

        payload = {
            'msg': 'method',
            'method': 'ctdb.public.ips.query',
        }
        res = make_ws_request(target[0], payload)
        assert res.get('error') is None, res

    for ip in CLUSTER_IPS:
        payload = {
            'msg': 'method',
            'method': 'ctdb.general.ips',
        }
        res = make_ws_request(ip, payload)
        assert res.get('error') is None, res
        public_ips = [x['public_ip'] for x in res['result']]
        assert to_remove not in public_ips


@pytest.mark.dependency(name='INTERFACE_ADDED')
@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_003_add_public_ip(ip, request):
    """
    This test adds the public IP that we removed
    back to each node (we deleted in previous test).
    """
    depends(request, ['INTERFACE_REMOVED'])
    payload = {
        'ip': PUBLIC_IPS[0],
        'netmask': CLUSTER_INFO['NETMASK'],
        'interface': CLUSTER_INFO['INTERFACE']
    }
    res = make_request('post', f'http://{ip}/api/v2.0/ctdb/public/ips', data=payload)
    try:
        status = wait_on_job(res.json(), ip, 5)
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status

    payload = {
        'msg': 'method',
        'method': 'ctdb.public.ips.query',
        'params': [[['pnn', '=', ifaces_nodemap[ip]['pnn']]], {'get': True}]
    }
    res = make_ws_request(ip, payload)
    assert res.get('error') is None, res

    configured_ips = set(res['result']['configured_ips'].keys())
    public_ips = set(PUBLIC_IPS)
    assert configured_ips == public_ips
