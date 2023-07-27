from config import CLUSTER_INFO, BRICK_PATH, GLUSTER_PEERS_DNS, CLUSTER_IPS, PUBLIC_IPS, TIMEOUTS
from utils import make_request, make_ws_request, wait_on_job
from helpers import ctdb_healthy
from exceptions import JobTimeOut

import json

GPD = GLUSTER_PEERS_DNS
URLS = [f'http://{ip}/api/v2.0' for ip in CLUSTER_IPS]


def create_cluster():
    peers_config = [{
        'private_address': CLUSTER_INFO[f'NODE_{node}_IP'],
        'hostname': CLUSTER_INFO[f'NODE_{node}_DNS'],
        'brick_path': BRICK_PATH,
        'remote_credential': {
            'username': CLUSTER_INFO['APIUSER'],
            'password': CLUSTER_INFO['APIPASS']
        }
    } for node in ('B', 'C')]

    local_node = {
        'private_address': CLUSTER_INFO['NODE_A_IP'],
        'hostname': CLUSTER_INFO['NODE_A_DNS'],
        'brick_path': BRICK_PATH,
    }

    # TODO: once we have more VMs available for cluster this
    # should be switched to a more reasonable brick configuration
    payload = {
        'msg': 'method',
        'method': 'cluster.management.cluster_create',
        'params': [{
            'volume_configuration': {
                'name': CLUSTER_INFO['GLUSTER_VOLUME'],
                'brick_layout': {'distribute_bricks': 3}
            },
            'local_node_configuration': local_node,
            'peers': peers_config,
        }]
    }
    res = make_ws_request(CLUSTER_INFO['NODE_A_IP'], payload)
    assert res.get('error') is None, str(res)

    try:
        status = wait_on_job(res['result'], CLUSTER_INFO['NODE_A_IP'], TIMEOUTS['VOLUME_TIMEOUT'])
    except JobTimeOut:
        assert False, JobTimeOut
    else:
        assert status['state'] == 'SUCCESS', status


def wait_on_ctdb():
    assert ctdb_healthy(timeout=300), 'CTDB Not healthy after 300 seconds'


def add_public_ips_to_ctdb():
    for priv_ip in CLUSTER_IPS:
        res = make_request('post', f'http://{priv_ip}/api/v2.0/ctdb/general/status', data={'all_nodes': False})
        this_node = res.json()['nodemap']['nodes'][0]['pnn']

        for pub_ip in PUBLIC_IPS:
            payload = {
                'pnn': this_node,
                'ip': pub_ip,
                'netmask': CLUSTER_INFO['NETMASK'],
                'interface': CLUSTER_INFO['INTERFACE']
            }
            res = make_request('post', f'http://{priv_ip}/api/v2.0/ctdb/public/ips', data=payload)
            assert res.status_code == 200, res.text
            try:
                status = wait_on_job(res.json(), priv_ip, TIMEOUTS['CTDB_IP_TIMEOUT'])
            except JobTimeOut:
                assert False, JobTimeOut
            else:
                assert status['state'] == 'SUCCESS', status

def generate_cluster_summary():
    res = make_ws_request(CLUSTER_INFO['NODE_A_IP'], {
        'msg': 'method',
        'method': 'cluster.management.summary',
        'params': []
    })
    assert res.get('error') is None, str(res)
    print(json.dumps(res['result'], indent=4))


def init():
    print('Creating cluster.')
    create_cluster()
    print('Waiting on CTDB to become healthy')
    wait_on_ctdb()
    print('Adding CTDB public IPs to cluster')
    add_public_ips_to_ctdb()
    print('Generating summary')
    generate_cluster_summary()
