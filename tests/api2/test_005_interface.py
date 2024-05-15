import sys
import time
import os
apifolder = os.getcwd()
sys.path.append(apifolder)

import pytest

from auto_config import interface, ha, netmask, user, password
from middlewared.test.integration.utils.client import client, truenas_server
from functions import SSH_TEST


@pytest.fixture(scope='module')
def ws_client():
    with client(host_ip=truenas_server.ip) as c:
        yield c


@pytest.fixture(scope='module')
def get_payload(ws_client):
    if ha:
        payload = {
            'ipv4_dhcp': False,
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
        to_validate = [os.environ['controller1_ip'], os.environ['virtual_ip']]
    else:
        # NOTE: on a non-HA system, this method is assuming
        # that the machine has been handed an IPv4 address
        # from a DHCP server. That's why we're getting this information.
        ans = ws_client.call('interface.query', [['name', '=', interface]], {'get': True})
        payload = {'ipv4_dhcp': False, 'aliases': []}
        to_validate = []
        ip = truenas_server.ip
        for info in filter(lambda x: x['address'] == ip, ans['state']['aliases']):
            payload['aliases'].append({'address': ip, 'netmask': info['netmask']})
            to_validate.append(ip)

        assert all((payload['aliases'], to_validate))

    return payload, to_validate

# Make sure that our initial conditions are met
def test_001_check_ipvx(request, ws_client, get_payload):
    # Verify that dhclient is running
    ps_count = int(SSH_TEST('ps -aux | grep dhclient | wc -l', user, password, truenas_server.ip)['stdout'])
    assert ps_count > 1 # account for the grep

    autoconf = int(SSH_TEST(f'cat /proc/sys/net/ipv6/conf/{interface}/autoconf', user, password, truenas_server.ip)['stdout'])
    # Check that our proc entry is set to default 1. Identical to tunable.get_sysctl
    assert autoconf == 1

def test_002_configure_interface(request, ws_client, get_payload):
    if ha:
        # can not make network changes on an HA system unless failover has
        # been explicitly disabled
        ws_client.call('failover.update', {'disabled': True, 'master': True})
        assert ws_client.call('failover.config')['disabled'] is True

    # send the request to configure the interface
    ws_client.call('interface.update', interface, get_payload[0])

    # 1. verify there are pending changes
    # 2. commit the changes specifying the rollback timer
    # 3. verify that the changes that were committed, need to be "checked" in (finalized)
    # 4. finalize the changes (before the temporary changes are rolled back) (i.e. checkin)
    # 5. verify that there are no more pending interface changes
    assert ws_client.call('interface.has_pending_changes')
    ws_client.call('interface.commit', {'rollback': True, 'checkin_timeout': 10})
    assert ws_client.call('interface.checkin_waiting')
    ws_client.call('interface.checkin')
    assert ws_client.call('interface.checkin_waiting') is None
    assert ws_client.call('interface.has_pending_changes') is False

    if ha:
        # on HA, keepalived is responsible for configuring the VIP so let's give it
        # some time to settle
        time.sleep(3)

    # We've configured the interface so let's make sure the ip addresses on the interface
    # match reality
    reality = set([i['address'] for i in ws_client.call('interface.ip_in_use', {'ipv4': True})])
    assert reality == set(get_payload[1])

    if ha:
        # let's go 1-step further and validate that the VIP accepts connections
        with client(host_ip=os.environ['virtual_ip']) as c:
            assert c.call('core.ping') == 'pong'
            assert c.call('failover.call_remote', 'core.ping') == 'pong'

        # it's very important to set this because the `tests/conftest.py` config
        # (that pytest uses globally for the entirety of CI runs) uses this IP
        # address and so we need to make sure it uses the VIP on HA systems
        truenas_server.ip = os.environ['virtual_ip']
        truenas_server.nodea_ip = os.environ['controller1_ip']
        truenas_server.nodeb_ip = os.environ['controller2_ip']
        truenas_server.server_type = os.environ['SERVER_TYPE']

def test_003_recheck_ipvx(request, ws_client, get_payload):
    autoconf = int(SSH_TEST(f'cat /proc/sys/net/ipv6/conf/{interface}/autoconf', user, password, truenas_server.ip)['stdout'])
    assert autoconf == 1
    payload = get_payload[0]
    payload['ipv6_auto'] = False
    ws_client.call('interface.update', interface, payload)
    time.sleep(5) # Prevent race conditions
    autoconf = int(SSH_TEST(f'cat /proc/sys/net/ipv6/conf/{interface}/autoconf', user, password, truenas_server.ip)['stdout'])
    assert autoconf == 0
    