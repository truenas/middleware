import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils import make_request, make_ws_request, wait_on_job
from config import CLUSTER_INFO, DATASET_HIERARCHY
from exceptions import JobTimeOut


JOB_TIMEOUT = 120  # number of seconds to wait on a job to complete


def setup_zpool_and_datasets(ip):
    result = {'ERROR': ''}

    # query for existing zpool (clean CI run creates a zpool)
    print(f'Checking for existing zpools on {ip}')
    url = f'http://{ip}/api/v2.0/pool'
    ans = make_request('get', url)
    if ans.status_code != 200:
        result['ERROR'] = f'Invalid status code when checking for existing zpools: {ans.text}'
        return result

    # get the id of the existing pool and export it
    pool = ans.json()
    pool = pool[0] if pool else None
    if pool:
        url = f'http://{ip}/api/v2.0/pool/id/{pool["id"]}/export'
        ans = make_request('post', url)
        if ans.status_code != 200:
            result['ERROR'] = f'Invalid status code when exporting "{pool["name"]}" on {ip}: {ans.text}'
            return result
        try:
            print(f'Waiting on "{pool["name"]}" to be exported on {ip}')
            status = wait_on_job(ans.json(), ip, JOB_TIMEOUT)
        except JobTimeOut:
            result['ERROR'] = f'Timed out waiting on "{pool["name"]}" to be exported on {ip}'
            return result
        else:
            if status['state'] != 'SUCCESS':
                result['ERROR'] = f'Exporting "{pool["name"]}" failed on {ip}'
                return result

    # wipe the disks to clean any remnants of previous zpools
    print(f'Wiping "{CLUSTER_INFO["ZPOOL_DISK"]}" on {ip}')
    url = f'http://{ip}/api/v2.0/disk/wipe'
    payload = {'dev': CLUSTER_INFO['ZPOOL_DISK'], 'mode': 'QUICK'}
    ans = make_request('post', url, data=payload)
    if ans.status_code != 200:
        result['ERROR'] = f'Invalid status code when wiping disk: {ans.status_code}:{ans.text}'
        return result
    try:
        print(f'Waiting for disk "{CLUSTER_INFO["ZPOOL_DISK"]}" on {ip} to be wiped')
        status = wait_on_job(ans.json(), ip, JOB_TIMEOUT)
    except JobTimeOut:
        result['ERROR'] = f'Timed out waiting for disk to be wiped on {ip}'
        return result
    else:
        if status['state'] != 'SUCCESS':
            result['ERROR'] = 'Wiping disk {CLUSTER_INFO["ZPOOL_DISK"]} failed on {ip}'
            return result

    # now create the zpool
    print(f'Creating zpool "{CLUSTER_INFO["ZPOOL"]}" on {ip}')
    url = f'http://{ip}/api/v2.0/pool'
    payload = {
        'name': CLUSTER_INFO['ZPOOL'],
        'encryption': False,
        'topology': {'data': [{'type': 'STRIPE', 'disks': [CLUSTER_INFO['ZPOOL_DISK']]}]},
        'allow_duplicate_serials': True,
    }
    ans = make_request('post', url, data=payload)
    if ans.status_code != 200:
        result['ERROR'] = f'Failed to create zpool: "{CLUSTER_INFO["ZPOOL"]}" on {ip}:{ans.text}'
        return result
    try:
        print(f'Waiting on zpool "{CLUSTER_INFO["ZPOOL"]}" to be created on {ip}')
        status = wait_on_job(ans.json(), ip, JOB_TIMEOUT)
    except JobTimeOut:
        result['ERROR'] = f'Timed out waiting on zpool to be created on {ip}'
        return result
    else:
        if status['state'] != 'SUCCESS':
            result['ERROR'] = f'Creating zpool was a failure: {status["result"]} on {ip}'
            return result

    # now create the cluster datasets, we have to use websocket here
    # because we're creating "internal" datasets that we prevent any
    # normal API user from creating using the public API so use websocket
    # API to side-step the public API validation
    print(f'Creating dataset hierarchy "{DATASET_HIERARCHY}" on {ip}')
    payload = {
        'msg': 'method',
        'method': 'zfs.dataset.create',
        'params': [{
            'name': DATASET_HIERARCHY,
            'type': 'FILESYSTEM',
            'create_ancestors': True,
            'properties': {'acltype': 'posix'}
        }]
    }
    res = make_ws_request(ip, payload)
    if res.get('error', {}):
        result['ERROR'] = res['error'].get('reason', 'NO REASON GIVEN')

    # libzfs doesn't mount the youngest ancestor when you give it a
    # path of ancestors to be created all at once. This means we have
    # mount the youngest ancestor
    # i.e. cargo/.glusterfs/gvol01/brick0 (brick0 needs to be mounted)
    print(f'Mounting dataset hierarchy "{DATASET_HIERARCHY}" on {ip}')
    payload = {
        'msg': 'method',
        'method': 'zfs.dataset.mount',
        'params': [DATASET_HIERARCHY],
    }
    res = make_ws_request(ip, payload)
    if res.get('error', {}):
        result['ERROR'] = res['error'].get('reason', 'NO REASON GIVEN')

    return result


def setup_network(ip):
    # the cluster nodes are assigned an IP
    # address via DHCP reservations, however,
    # it's a prerequisite that the peers in
    # the cluster have static IP addresses
    result = {'ERROR': ''}

    # setup router/dns/defgw first
    print(f'Setting up default gateway and dns on {ip}')
    url = f'http://{ip}/api/v2.0/network/configuration'
    payload = {'ipv4gateway': CLUSTER_INFO['DEFGW'], 'nameserver1': CLUSTER_INFO['DNS1']}
    ans = make_request('put', url, data=payload)
    if ans.status_code != 200:
        result['ERROR'] = f'Failed to configure gateway on {ip}:{ans.text}'
        return result

    # setup the static IP address
    print(f'Setting up static ip on {ip}')
    url = f'http://{ip}/api/v2.0/interface/id/{CLUSTER_INFO["INTERFACE"]}'
    payload = {
        'ipv4_dhcp': False,
        'aliases': [{
            'address': ip,
            'netmask': CLUSTER_INFO['NETMASK'],
        }],
    }
    ans = make_request('put', url, data=payload)
    if ans.status_code != 200:
        result['ERROR'] = f'Failed to configure static IP information for {ip}:{ans.text}'
        return result

    # commit changes
    print(f'Commit network changes on {ip}')
    url = f'http://{ip}/api/v2.0/interface/commit'
    payload = {'rollback': True, 'checkin_timeout': 5}
    ans = make_request('post', url, data=payload)
    if ans.status_code != 200:
        result['ERROR'] = f'Failed to commit static IP information for {ip}:{ans.text}'
        return result

    # checkin the changes (finalize them)
    print(f'Checkin network changes on {ip}')
    url = f'http://{ip}/api/v2.0/interface/checkin'
    ans = make_request('get', url)
    if ans.status_code != 200:
        result['ERROR'] = 'Failed to commit static IP information for {ip}:{ans.text}'
        return result

    return result


def get_os_version(ip):
    # the os versions for all peers need to match
    # or we're going to have a bad time
    result = {'IP': ip, 'ERROR': '', 'VERS': ''}

    print(f'Getting OS version on {ip}')
    ans = make_request('get', f'http://{ip}/api/v2.0/system/version')
    if ans.status_code == 200:
        result['VERS'] = ans.text
    else:
        result['ERROR'] = f'Got invalid status_code: {ans.status_code} for IP: {ip}'

    return result


def init():
    with ThreadPoolExecutor() as exc:
        nodes_ip_keys = ('NODE_A_IP', 'NODE_B_IP', 'NODE_C_IP')
        ips = [v for k, v in CLUSTER_INFO.items() if k in nodes_ip_keys]
        errors = []

        # First, setup the network
        futures = [exc.submit(setup_network, ip) for ip in ips]
        for fut in as_completed(futures):
            res = fut.result()
            errors.append(res['ERROR']) if res['ERROR'] else None
        if errors:
            for error in errors:
                # means the network setup failed on at least
                # one of the peers
                print(error)
            sys.exit(2)

        # Second, verify the OS versions match
        futures = [exc.submit(get_os_version, ip) for ip in ips]
        versions = set()
        for fut in as_completed(futures):
            res = fut.result()
            if res['ERROR']:
                errors.append(res['ERROR'])
            else:
                versions.add((res['IP'], res['VERS']))
        if errors:
            for error in errors:
                # means unable to determine OS version betwen all peers
                print(error)
            sys.exit(2)
        elif len(set([i[1] for i in versions])) > 1:
            # means OS versions do not match between all peers
            print(f'Version of software installed on each peer is not the same: {versions}')
            sys.exit(2)

        # Finally, setup the zpools and datasets
        futures = [exc.submit(setup_zpool_and_datasets, ip) for ip in ips]
        for fut in as_completed(futures):
            res = fut.result()
            errors.append(res['ERROR']) if res['ERROR'] else None
        if errors:
            for error in errors:
                # means the zpool or cluster datasets failed to be setup
                print(error)
            sys.exit(2)
