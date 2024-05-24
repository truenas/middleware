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
    finally:
        config_set_hostname(current_hostname)
        assert fetch_hostname() == current_hostname
