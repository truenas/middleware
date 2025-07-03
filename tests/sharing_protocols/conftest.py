import os
import time

from auto_config import domain, gateway, ha, ha_license, hostname, interface, netmask
from middlewared.test.integration.utils import call, fail, pool, truenas_server


def setup_ssh():
    root_id = call('user.query', [['username', '=', 'root']], {'get': True})['id']
    call('user.update', root_id, {'ssh_password_enabled': True})
    call('service.start', 'ssh')
    call('service.update', 'ssh', {'enable': True})
    call('ssh.update', {'passwordauth': True})


def apply_and_verify_license():
    if ha_license:
        _license_string = ha_license
    else:
        with open(os.environ.get('license_file', '/root/license.txt')) as f:
            _license_string = f.read()

    # apply license
    call('system.license_update', _license_string)

    # verify license is applied
    assert call('failover.licensed') is True

    retries = 30
    sleep_time = 1
    for i in range(retries):
        if call('failover.call_remote', 'failover.licensed') is False:
            # we call a hook that runs in a background task
            # so give it a bit to propagate to other controller
            # furthermore, our VMs are...well...inconsistent to say the least
            # so sometimes this is almost instant while others I've 10+ secs
            time.sleep(sleep_time)
        else:
            break
    else:
        assert False, 'Timed out after waiting on license to sync to standby'


def set_netinfo():
    info = {
        'domain': domain,
        'ipv4gateway': gateway,
        'hostname': os.environ['hostname'],
        'hostname_b': os.environ['hostname_b'],
        'hostname_virtual': os.environ['hostname_virtual'],
        'nameserver1': os.environ['primary_dns'],
        'nameserver2': os.environ.get('secondary_dns', ''),
    }

    call('network.configuration.update', info)
    call('smb.update', {'netbiosname': info['hostname_virtual']})


def set_netinfo_single():
    call('smb.update', {'netbiosname': hostname})
    call('network.configuration.update', {'hostname': hostname})


def set_interfaces():
    payload = {
        'ipv4_dhcp': False,
        'ipv6_auto': False,
        'failover_critical': True,
        'failover_group': 1,
        'aliases': [
            {
                'type': 'INET',
                'address': os.environ['controller1_ip'],
                'netmask': int(netmask)
            }
        ],
        'failover_aliases': [
            {
                'type': 'INET',
                'address': os.environ['controller2_ip'],
            }
        ],
        'failover_virtual_aliases': [
            {
                'type': 'INET',
                'address': os.environ['virtual_ip'],
            }
        ],
    }
    call('failover.update', {'disabled': True, 'master': True})
    call('interface.update', interface, payload)
    call('interface.commit')
    call('interface.checkin')

    time.sleep(3)
    truenas_server.ip = os.environ['virtual_ip']
    truenas_server.nodea_ip = os.environ['controller1_ip']
    truenas_server.nodeb_ip = os.environ['controller2_ip']
    truenas_server.server_type = os.environ['SERVER_TYPE']

    # Make extra sure the configuration is synced to VM and we reboot
    try:
        call('failover.sync_to_peer', {'reboot': True})
    except Exception:
        pass


def create_permanent_pool():
    # Create a pool if one doesn't already exist
    if [] == call('pool.query', [["name", "=", pool]]):
        unused_disks = call('disk.get_unused')
        assert len(unused_disks) > 0
        call('pool.create', {
            'name': pool,
            'topology': {
                'data': [{
                    'type': 'STRIPE', 'disks': [unused_disks[0]['name']]
                }]
            }
        }, job=True)

    if ha:
        call('failover.update', {'disabled': False, 'master': True})


def setup_server_ha():
    stage = None
    try:
        stage = 'SETUP_SSH'
        setup_ssh()
        stage = 'APPLY_LICENSE'
        apply_and_verify_license()
        stage = 'SETUP_NETINFO'
        set_netinfo()
        stage = 'SETUP_INTERFACES'
        set_interfaces()
        stage = 'SETUP_POOL'
        create_permanent_pool()
    except Exception as exc:
        fail(f'{stage}: failed to set up truenas server: {exc}')


def setup_server_single():
    stage = None
    try:
        stage = 'SETUP_SSH'
        setup_ssh()
        stage = 'SETUP_NETINFO'
        set_netinfo_single()
        stage = 'SETUP_POOL'
        create_permanent_pool()
    except Exception as exc:
        fail(f'{stage}: failed to set up truenas server: {exc}')


def pytest_sessionstart(session):
    setup_fn = setup_server_ha if ha else setup_server_single
    setup_fn()
