import pprint
import pytest

from config import CLIENT_AUTH, CLUSTER_IPS, TIMEOUTS
from pytest_dependency import depends
from time import sleep
from utils import ssh_test
from middlewared.test.integration.utils import client
from helpers import client_and_events


MIDDLEWARE_EVENT_SCRIPT = '/etc/ctdb/events/legacy/80.truenas_middlewared.script'


# The CTDB daemon supports event scripts that are triggered
# on certain events (such as startup, monitoring, recovery, and IP
# allocation). The TrueNAS SCALE middleware has its own custom ctdb
# event script (80.truenas_middlewared.script) that will generate
# middleware events that may be subscribed to by via `ctdb.status`.
# Some events may be emitted by all cluster nodes, and other ones
# will only be sent by the cluster leader. The following series of
# tests validates that the events are sent in appropriate
# circumstances and are only sent by the correct cluster member.


@pytest.mark.dependency(name='EVENT_SCRIPTS_ENABLED')
@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_001_check_middleware_script_set(ip, request):
    with client(auth=CLIENT_AUTH, host_ip=ip) as c:
        st = c.call('filesystem.stat', MIDDLEWARE_EVENT_SCRIPT)
        assert st['type'] == 'SYMLINK'
        assert st['realpath'] == '/usr/share/ctdb/events/legacy/80.truenas_middlewared.script'


@pytest.mark.dependency(name='CLUSTER_LEADER_KNOWN')
@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_002_check_become_leader_event(ip, request):
    """
    The cluster leader event gets called directly from our reclock helper
    script when it manages to grab the recovery lock. This simulates by doing
    the same thing (making call to ctdb.event.process).

    There is no filtering based on whether current node is leader.
    """
    depends(request, ['EVENT_SCRIPTS_ENABLED'])
    global cluster_leader

    with client_and_events(ip) as conn:
        c, events = conn
        c.call('ctdb.event.process', {'event': 'LEADER', 'status': 'SUCCESS'})
        sleep(10)

    assert len(events) == 1, pprint.pformat(events, indent=2)

    ev = events[0]
    assert ev[0] == 'CHANGED', pprint.pformat(events, indent=2)
    assert ev[1]['collection'] == 'ctdb.status', pprint.pformat(ev[1], indent=2)

    fields = ev[1]['fields']
    assert 'data' in fields, pprint.pformat(fields, indent=2)
    assert fields.get('event') == 'LEADER', pprint.pformat(fields, indent=2)
    cluster_leader = fields['data']['leader']


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_003_check_ip_reallocate_event(ip, request):
    depends(request, ['CLUSTER_LEADER_KNOWN'])

    with client_and_events(ip) as conn:
        event_expected = ip == cluster_leader['private_address']
        c, events = conn
        res = ssh_test(ip, f'{MIDDLEWARE_EVENT_SCRIPT} ipreallocated')
        assert res['result'] is True, str(res)
        sleep(10)

        assert bool(events) is event_expected, pprint.pformat(events, indent=2)

        if event_expected:
            assert len(events) == 1, pprint.pformat(events, indent=2)
            ev = events[0]
            assert ev[0] == 'CHANGED', pprint.pformat(events, indent=2)
            assert ev[1]['collection'] == 'ctdb.status', pprint.pformat(ev[1], indent=2)
            fields = ev[1]['fields']
            assert 'data' in fields, pprint.pformat(fields, indent=2)
            assert fields.get('event') == 'IPREALLOCATED', pprint.pformat(fields, indent=2)



@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_004_start_recovery_event(ip, request):
    depends(request, ['CLUSTER_LEADER_KNOWN'])

    with client_and_events(ip) as conn:
        event_expected = ip == cluster_leader['private_address']
        c, events = conn
        res = ssh_test(ip, f'{MIDDLEWARE_EVENT_SCRIPT} startrecovery')
        assert res['result'] is True, str(res)
        sleep(10)

        assert bool(events) is event_expected, pprint.pformat(events, indent=2)

        if event_expected:
            assert len(events) == 1, pprint.pformat(events, indent=2)
            ev = events[0]
            assert ev[0] == 'CHANGED', pprint.pformat(events, indent=2)
            assert ev[1]['collection'] == 'ctdb.status', pprint.pformat(ev[1], indent=2)
            fields = ev[1]['fields']
            assert 'data' in fields, pprint.pformat(fields, indent=2)
            assert fields.get('event') == 'STARTRECOVERY', pprint.pformat(fields, indent=2)


@pytest.mark.parametrize('ip', CLUSTER_IPS)
def test_005_recovered_event(ip, request):
    depends(request, ['CLUSTER_LEADER_KNOWN'])

    with client_and_events(ip) as conn:
        event_expected = ip == cluster_leader['private_address']
        c, events = conn
        res = ssh_test(ip, f'{MIDDLEWARE_EVENT_SCRIPT} recovered')
        assert res['result'] is True, str(res)
        sleep(10)

        assert bool(events) is event_expected, pprint.pformat(events, indent=2)

        if event_expected:
            assert len(events) == 1, pprint.pformat(events, indent=2)
            ev = events[0]
            assert ev[0] == 'CHANGED', pprint.pformat(events, indent=2)
            assert ev[1]['collection'] == 'ctdb.status', pprint.pformat(ev[1], indent=2)
            fields = ev[1]['fields']
            assert 'data' in fields, pprint.pformat(fields, indent=2)
            assert fields.get('event') == 'RECOVERED', pprint.pformat(fields, indent=2)
