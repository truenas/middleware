import sys
import time
import os
apifolder = os.getcwd()
sys.path.append(apifolder)

import pytest

from auto_config import ip, interface, ha, netmask
from middlewared.test.integration.utils.client import client


@pytest.fixture(scope='module')
def ws_client():
    with client(host_ip=ip) as c:
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
        for info in filter(lambda x: x['address'] == ip, ans['state']['aliases']):
            payload['aliases'].append({'address': ip, 'netmask': info['netmask']})
            to_validate.append(ip)

        assert all((payload['aliases'], to_validate))

    return payload, to_validate


def test_001_configure_interface(request, ws_client, get_payload):
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
        # (that pytest uses globally for the entirety of CI runs) will check this
        # value and use the proper IP address (the VIP) on HA systems
        os.environ['USE_VIP'] = 'YES'
