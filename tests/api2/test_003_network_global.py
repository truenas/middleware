import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)

import pytest
from pytest_dependency import depends

from auto_config import ha, interface, hostname, domain, ip
from middlewared.test.integration.utils.client import client

pytestmark = pytest.mark.base


@pytest.fixture(scope='module')
def ip_to_use():
    return ip if not ha else os.environ['controller1_ip']


@pytest.fixture(scope='module')
def ws_client(ip_to_use):
    with client(host_ip=ip_to_use) as c:
        yield c


@pytest.fixture(scope='module')
def netinfo(ws_client):
    domain_to_use = domain
    hosts = ['192.168.1.150 fakedomain.doesnt.exist', '172.16.50.100 another.fakeone']
    if ha and (domain_to_use := os.environ.get('domain', None)) is not None:
        info = {
            'domain': domain_to_use,
            'ipv4gateway': os.environ['gateway'],
            'hostname': os.environ['hostname'],
            'hostname_b': os.environ['hostname_b'],
            'hostname_virtual': os.environ['hostname_virtual'],
            'nameserver1': os.environ['primary_dns'],
            'nameserver2': os.environ.get('secondary_dns', ''),
            'hosts': hosts,
        }
    else:
        # NOTE: on a non-HA system, this method is assuming
        # that the machine has been handed a default route
        # and nameserver(s) from a DHCP server. That's why
        # we're getting this information.
        ans = ws_client.call('network.general.summary')
        assert isinstance(ans, dict)
        assert isinstance(ans['default_routes'], list) and ans['default_routes']
        assert isinstance(ans['nameservers'], list) and ans['nameservers']
        info = {'domain': domain_to_use, 'hostname': hostname, 'ipv4gateway': ans['default_routes'][0], 'hosts': hosts}
        for idx, nameserver in enumerate(ans['nameservers'], start=1):
            if idx > 3:
                # only 3 nameservers allowed via the API
                break
            info[f'nameserver{idx}'] = nameserver

    return info


@pytest.mark.dependency(name='NET_CONFIG')
def test_001_set_and_verify_network_global_settings_database(ws_client, netinfo):
    config = ws_client.call('network.configuration.update', netinfo)
    assert all(config[k] == netinfo[k] for k in netinfo)


def test_002_verify_network_global_settings_state(request, ws_client, netinfo):
    depends(request, ['NET_CONFIG'])
    state = ws_client.call('network.configuration.config')['state']
    assert set(state['hosts']) == set(netinfo['hosts'])
    assert state['ipv4gateway'] == netinfo['ipv4gateway']
    for key in filter(lambda x: x.startswith('nameserver'), netinfo):
        assert state[key] == netinfo[key]

    """
    HA isn't fully operational by the time this test runs so testing
    the functionality on the remote node is guaranteed to fail. We
    should probably rearrange order of tests and fix this at some point.
    if ha:
        state = ws_client.call('failover.call_remote', 'network.configuration.config')['state']
        assert set(state['hosts']) == set(netinfo['hosts'])
        assert state['ipv4gateway'] == netinfo['ipv4gateway']
        for key in filter(lambda x: x.startswith('nameserver'), netinfo):
            assert state[key] == netinfo[key]
    """


@pytest.mark.dependency(name='GENERAL')
def test_003_verify_network_general_summary(request, ws_client, netinfo, ip_to_use):
    depends(request, ['NET_CONFIG'])
    summary = ws_client.call('network.general.summary')
    assert any(i.startswith(ip_to_use) for i in summary['ips'][interface]['IPV4'])
