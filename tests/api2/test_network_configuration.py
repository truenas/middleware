import time

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import call, ssh

from auto_config import ha

NEW_HOSTNAME = 'dummy123'


def fetch_hostname():
    name = ssh('hostname').strip()
    if ha:
        return name.removesuffix('-nodea').removesuffix('-nodeb')
    return name


def config_read_hostname():
    config = call('network.configuration.config')
    if ha:
        return config['hostname_virtual']
    else:
        return config['hostname']


def config_set_hostname(name):
    if ha:
        payload = {'hostname': f'{name}-nodea',
                   'hostname_b': f'{name}-nodeb',
                   'hostname_virtual': name}
    else:
        payload = {'hostname': name}
    call('network.configuration.update', payload)


def test_changing_hostname():
    current_hostname = config_read_hostname()

    config_set_hostname(NEW_HOSTNAME)
    try:
        assert fetch_hostname() == NEW_HOSTNAME
        assert ssh('getent hosts "$(hostname)"', check=False).startswith('127.0.0.1')
    finally:
        config_set_hostname(current_hostname)
        assert fetch_hostname() == current_hostname
        assert ssh('getent hosts "$(hostname)"', check=False).startswith('127.0.0.1')


def test_hosts_file_without_earmarker_reports_no_static_entries():
    original_hosts = call('network.configuration.config')['hosts']
    call('network.configuration.update', {'hosts': ['192.0.2.10 static-entry.example']})
    try:
        ssh("sed -i '/^# STATIC ENTRIES$/d' /etc/hosts")
        assert '192.0.2.10 static-entry.example' in ssh('cat /etc/hosts')
        assert call('network.configuration.config')['state']['hosts'] == []
    finally:
        call('network.configuration.update', {'hosts': original_hosts})


@pytest.mark.parametrize('payload,attribute,errmsg', [
    (
        {'nameserver1': '0.0.0.0'},
        'global_configuration_update.nameserver1',
        'Unspecified addresses are not valid as nameservers',
    ),
    (
        {'nameserver1': '255.255.255.255'},
        'global_configuration_update.nameserver1',
        'This is not a valid nameserver address',
    ),
    (
        {'nameserver1': '169.254.1.1'},
        'global_configuration_update.nameserver1',
        '169.254/16 subnet is not valid for nameserver',
    ),
    (
        {'nameserver1': '192.0.2.1', 'nameserver3': '192.0.2.3'},
        'global_configuration_update.nameserver',
        'When providing nameservers, they must be provided in consecutive order '
        '(i.e. nameserver1, nameserver2, nameserver3)',
    ),
    (
        {'ipv4gateway': '192.0.2.1'},
        'global_configuration_update.ipv4gateway',
        'Gateway 192.0.2.1 is unreachable',
    ),
    (
        {'domains': ['a.example', 'b.example', 'c.example', 'd.example', 'e.example', 'f.example']},
        'global_configuration_update.domains',
        'No more than 5 additional domains are allowed',
    ),
])
def test_update_validation(payload, attribute, errmsg):
    with pytest.raises(ValidationErrors) as ve:
        call('network.configuration.update', payload)

    assert [(e.attribute, e.errmsg) for e in ve.value.errors] == [(attribute, errmsg)]


def test_time_machine_share_requires_mdns():
    with dataset('tm_mdns', {'share_type': 'SMB'}) as ds:
        with smb_share(f'/mnt/{ds}', 'tm_mdns', {'purpose': 'TIMEMACHINE_SHARE'}):
            with pytest.raises(ValidationErrors) as ve:
                call('network.configuration.update', {'service_announcement': {'mdns': False}})

    assert [(e.attribute, e.errmsg) for e in ve.value.errors] == [(
        'global_configuration_update.service_announcement.mdns',
        'NAS is configured as a time machine target. mDNS is required.',
    )]


def test_httpproxy_reaches_middleware_environment():
    original_httpproxy = call('network.configuration.config')['httpproxy']
    call('network.configuration.update', {'httpproxy': 'http://192.0.2.1:3128'})
    try:
        # A network.config event handler sets the environment after the update returns
        for _ in range(10):
            if call('core.environ')['http_proxy'] == 'http://192.0.2.1:3128':
                break
            time.sleep(1)

        environ = call('core.environ')
        assert environ['http_proxy'] == 'http://192.0.2.1:3128'
        assert environ['https_proxy'] == 'http://192.0.2.1:3128'
    finally:
        call('network.configuration.update', {'httpproxy': original_httpproxy})


def test_unchanged_update_does_not_restart_discovery():
    pid = ssh('systemctl show --property MainPID --value truenas-discoveryd').strip()
    assert pid != '0'

    call('network.configuration.update', {'hostname': call('network.configuration.config')['hostname']})

    assert ssh('systemctl show --property MainPID --value truenas-discoveryd').strip() == pid
