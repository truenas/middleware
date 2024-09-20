import errno

import pytest
from pytest_dependency import depends

from functions import SSH_TEST
from auto_config import ha, user, password
from middlewared.service_exception import CallError
from middlewared.test.integration.assets.account import unprivileged_user
from middlewared.test.integration.utils import call, client


@pytest.fixture(scope='module')
def readonly_admin():
    # READONLY role implies FAILOVER_READ
    with unprivileged_user(
        username='failover_guy',
        group_name='failover_admins',
        privilege_name='FAILOVER_PRIV',
        allowlist=[],
        web_shell=False,
        roles=['READONLY_ADMIN']
    ) as acct:
        yield acct


@pytest.mark.dependency(name='hactl_install_dir')
def test_01_check_hactl_installed(request):
    rv = SSH_TEST('which hactl', user, password)
    assert rv['stdout'].strip() == '/usr/local/sbin/hactl', rv['output']


@pytest.mark.dependency(name='hactl_status')
def test_02_check_hactl_status(request):
    depends(request, ['hactl_install_dir'])
    rv = SSH_TEST('hactl', user, password)
    output = rv['stdout'].strip()
    if ha:
        for i in ('Node status:', 'This node serial:', 'Other node serial:', 'Failover status:'):
            assert i in output, output
    else:
        assert 'Not an HA node' in output, output


@pytest.mark.dependency(name='hactl_takeover')
def test_03_check_hactl_takeover(request):
    # integration tests run against the master node (at least they should...)
    depends(request, ['hactl_status'])
    rv = SSH_TEST('hactl takeover', user, password)
    output = rv['stdout'].strip()
    if ha:
        assert 'This command can only be run on the standby node.' in output, output
    else:
        assert 'Not an HA node' in output, output


@pytest.mark.dependency(name='hactl_enable')
def test_04_check_hactl_enable(request):
    # integration tests run against the master node (at least they should...)
    depends(request, ['hactl_takeover'])
    rv = SSH_TEST('hactl enable', user, password)
    output = rv['stdout'].strip()
    if ha:
        assert 'Failover already enabled.' in output, output
    else:
        assert 'Not an HA node' in output, output


def test_05_check_hactl_disable(request):
    depends(request, ['hactl_enable'])
    rv = SSH_TEST('hactl disable', user, password)
    output = rv['stdout'].strip()
    if ha:
        assert 'Failover disabled.' in output, output
        assert call('failover.config')['disabled'] is True
        rv = SSH_TEST('hactl enable', user, password)
        output = rv['stdout'].strip()
        assert 'Failover enabled.' in output, output
        assert call('failover.config')['disabled'] is False
    else:
        assert 'Not an HA node' in output, output


if ha:
    def test_07_failover_replicate():
        old_ns = call('network.configuration.config')['nameserver3']
        new_ns = '1.1.1.1'
        try:
            call('network.configuration.update', {'nameserver3': new_ns})

            remote = call('failover.call_remote', 'network.configuration.config')
            assert remote['nameserver3'] == new_ns
            assert remote['state']['nameserver3'] == new_ns
        finally:
            call('network.configuration.update', {'nameserver3': old_ns})
            remote = call('failover.call_remote', 'network.configuration.config')
            assert remote['nameserver3'] == old_ns
            assert remote['state']['nameserver3'] == old_ns

    def test_08_readonly_ops(request, readonly_admin):
        with client(auth=(readonly_admin.username, readonly_admin.password)) as c:
            c.call('failover.config')
            c.call('failover.node')
            with pytest.raises(CallError) as ce:
                c.call('failover.call_remote', 'user.update')

            assert ce.value.errno == errno.EACCES
