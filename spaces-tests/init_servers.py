import sys
from config import SPACES_CONFIG
from concurrent.futures import ThreadPoolExecutor, as_completed
from middlewared.test.integration.utils import client
from utils import spaces_connections
from time import sleep


def setup_zpool_and_datasets(c, member):
    # query for existing zpool (clean CI run creates a zpool)
    print(f'Checking for existing zpools on {member.ip}')
    where = None
    try:
        where = "export"
        pool = c.call('pool.query')
        if pool:
            c.call('pool.export', pool[0]['id'], job=True)

        where = "wipe"
        # wipe the disks to clean any remnants of previous zpools
        print(f'Wiping "{SPACES_CONFIG["ZPOOL_DISK"]}" on {member.ip}')
        c.call('disk.wipe', SPACES_CONFIG['ZPOOL_DISK'], 'QUICK', job=True)

        # now create the zpool
        where = "pool create"
        print(f'Creating zpool "{member.zpool}" on {member.ip}')
        pool_create = c.call('pool.create', {
            'name': member.zpool,
            'encryption': False,
            'topology': {'data': [{
                'type': 'STRIPE',
                'disks': [SPACES_CONFIG['ZPOOL_DISK']]}
            ]},
            'allow_duplicate_serials': True,
        # }, job=True)
        })
        while (j := c.call(
            'core.get_jobs', [['id', '=', pool_create]], {'get': True}
        ))['state'] == 'RUNNING':
            sleep(1)

        if j.get('error'):
            return {'error': j['error'], 'where': where, 'node': member.node, 'ip': member.ip}

    except Exception as e:
        return {'error': e, 'where': where, 'node': member.node, 'ip': member.ip}

    return {'result': member.zpool, 'node': member.node, 'ip': member.ip}


def setup_network(c, member):
    # the cluster nodes are assigned an IP
    # address via DHCP reservations, however,
    # it's a prerequisite that the peers in
    # the cluster have static IP addresses
    # setup router/dns/defgw first
    print(f'Setting up default gateway and dns on {member.ip}')
    c.call('network.configuration.update', {
        'ipv4gateway': SPACES_CONFIG['DEFGW'],
        'nameserver1': SPACES_CONFIG['DNS1']
    })

    # setup the static IP address
    print(f'Setting up static ip on {member.ip}')
    c.call('interface.update', SPACES_CONFIG['INTERFACE'], {
        'ipv4_dhcp': False,
        'aliases': [{
            'address': member.ip,
            'netmask': SPACES_CONFIG['NETMASK'],
        }],
    })

    # commit changes
    print(f'Commit network changes on {member.ip}')
    c.call('interface.commit', {
        'rollback': True, 'checkin_timeout': 5
    })

    # checkin the changes (finalize them)
    print(f'Checkin network changes on {member.ip}')
    c.call('interface.checkin')

    print(f'Allowing root SSH {member.ip}')
    c.call('user.update', 1, {'ssh_password_enabled': True})

    print(f'Enabling SSH on boot {member.ip}')
    c.call('service.update', 'ssh', {'enable': True})

    print(f'Starting SSH {member.ip}')
    c.call('service.start', 'ssh', {'silent': False})


def get_os_version(c, member):
    # the os versions for all peers need to match
    # or we're going to have a bad time

    print(f'Getting OS version on {member.ip}')
    return c.call('system.version')


def init():
    with spaces_connections() as connections:
        with ThreadPoolExecutor() as exc:
            # First, setup the network
            futures = [exc.submit(setup_network, *c) for c in connections]
            for fut in as_completed(futures):
                res = fut.result()

            # Second, verify the OS versions match
            futures = [exc.submit(get_os_version, *c) for c in connections]
            versions = set()
            for fut in as_completed(futures):
                versions.add(fut.result())

            if len(set([i[1] for i in versions])) > 1:
                # means OS versions do not match between all peers
                print(f'Version of software installed on each peer is not the same: {versions}')
                sys.exit(2)

            # Finally, setup the zpools and datasets
            futures = [exc.submit(setup_zpool_and_datasets, *c) for c in connections]
            for fut in as_completed(futures):
                res = fut.result()
                if res.get('error'):
                    print(f'Node {res["node"]}, address {res["ip"]}: Failed to set up pools [{res["where"]}]: {res["error"]}')
                    sys.exit(2)
                else:
                    print(f'Node {res["node"]}, address {res["ip"]}: pool setup completed')
