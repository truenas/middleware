from concurrent.futures import ThreadPoolExecutor, as_completed

from config import CLUSTER_INFO, BRICK_PATH, GLUSTER_PEERS_DNS, CLUSTER_IPS, PUBLIC_IPS, TIMEOUTS
from utils import make_request, wait_on_job
from helpers import ctdb_healthy
from exceptions import JobTimeOut

GPD = GLUSTER_PEERS_DNS
URLS = [f'http://{hostname}/api/v2.0' for hostname in GPD]


def enable_and_start_service_on_all_nodes():
    """enable and start glusterd service on all nodes in cluster"""
    with ThreadPoolExecutor() as exc:
        # enable the services
        urls = [url + '/service/id/glusterd' for url in URLS]
        payload = {'enable': True}
        futures = {exc.submit(make_request, 'put', url, data=payload): url for url in urls}

        results = {}
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result()

        assert all(v.status_code == 200 for k, v in results.items()), results

        # verify services are enabled
        urls = [url + '/service?service=glusterd' for url in URLS]
        futures = {exc.submit(make_request, 'get', url): url for url in urls}

        results = {}
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result().json()[0]['enable']

        assert all(v is True for k, v in results.items()), results

        # start the services
        urls = [url + '/service/start' for url in URLS]
        payload = {'service': 'glusterd'}
        futures = {exc.submit(make_request, 'post', url, data=payload): url for url in urls}

        results = {}
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result()

        assert all(v.status_code == 200 and v.json() is True for k, v in results.items()), results

        # verify the services are started
        urls = [url + '/service/?service=glusterd' for url in URLS]
        futures = {exc.submit(make_request, 'get', url): url for url in urls}

        results = {}
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result()

        assert all(v.status_code == 200 and v.json()[0]['state'] == 'RUNNING' for k, v in results.items()), results


def add_peers():
    """
    Add the peers to the TSP (Trusted Storage Pool). We choose a single
    node to send these requests since glusterd coordinates the network
    requests to the other nodes.
    """
    nodes = [v for k, v in CLUSTER_INFO.items() if k in ('NODE_B_DNS', 'NODE_C_DNS')]
    for node in nodes:
        # start the job to add a peer
        ans = make_request('post', f'http://{CLUSTER_INFO["NODE_A_IP"]}/api/v2.0/gluster/peer', data={'hostname': node})
        assert ans.status_code == 200, ans.text

        # wait on the peer to be added
        try:
            status = wait_on_job(ans.json(), CLUSTER_INFO['NODE_A_IP'], TIMEOUTS['CTDB_IP_TIMEOUT'])
        except JobTimeOut:
            assert False, JobTimeOut
        else:
            assert status['state'] == 'SUCCESS', status

    # query a node for the peers (it returns all peer information)
    ans = make_request('get', '/gluster/peer')
    assert ans.status_code == 200, ans.text
    # use casefold() for purpose of hostname validation sense case does not matter
    # but the resolvable names on the network might not match _exactly_ with what
    # was given to us in the config (i.e. DNS1.HOSTNAME.BLAH == DNS1.hostname.BLAH)
    assert set([i['hostname'].casefold() for i in ans.json()]) == set([i.casefold() for i in GPD]), ans.json()


def add_jwt_secret():
    """add the jwt secret to all nodes in the cluster"""
    with ThreadPoolExecutor() as exc:
        # add the secret to all nodes
        urls = [url + '/gluster/localevents/add_jwt_secret' for url in URLS]
        payload = {'secret': CLUSTER_INFO['APIPASS'], 'force': True}
        futures = {exc.submit(make_request, 'post', url, data=payload): url for url in urls}

        results = {}
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result()

        assert all(v.status_code == 200 for k, v in results.items()), results

        # verify the secret on all nodes
        urls = [url + '/gluster/localevents/get_set_jwt_secret' for url in URLS]
        futures = {exc.submit(make_request, 'get', url): url for url in urls}

        results = {}
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result()

        assert all(v.status_code == 200 and v.json() == CLUSTER_INFO['APIPASS'] for k, v in results.items()), results


def create_volume():
    """Create and start the gluster volume."""
    gvol = CLUSTER_INFO['GLUSTER_VOLUME']
    payload = {
        'name': gvol,
        'bricks': [{'peer_name': hostname, 'peer_path': BRICK_PATH} for hostname in GPD],
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
    payload = {'query-filters': [['name', '=', gvol]]}
    ans = make_request('get', '/gluster/volume', data=payload)
    assert ans.status_code == 200, ans.text
    assert len(ans.json()) > 0 and ans.json()[0]['id'] == gvol, ans.text


def wait_on_ctdb():
    assert ctdb_healthy(timeout=30), 'CTDB Not healthy after 30 seconds'


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
            try:
                status = wait_on_job(res.json(), priv_ip, TIMEOUTS['CTDB_IP_TIMEOUT'])
            except JobTimeOut:
                assert False, JobTimeOut
            else:
                assert status['state'] == 'SUCCESS', status


def init():
    print('Enabling and starting "glusterd" service on all nodes.')
    enable_and_start_service_on_all_nodes()
    print('Adding peers to the trusted storage pool.')
    add_peers()
    print('Adding JWT secret to all nodes')
    add_jwt_secret()
    print('Creating gluster volume')
    create_volume()
    print('Waiting on CTDB to become healthy')
    wait_on_ctdb()
    print('Adding CTDB public IPs to cluster')
    add_public_ips_to_ctdb()
