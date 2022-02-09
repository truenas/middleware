import pytest

from middlewared.test.integration.utils import call, ssh

import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import dev_test
reason = 'Skip for testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)


def test_enabling_serial_port():
    ports = call('system.advanced.serial_port_choices')
    assert 'ttyS0' in ports, ports

    for port in ports:
        test_config = {'serialconsole': True, 'serialport': port}
        config = call('system.advanced.update', test_config)
        for k, v in test_config.items():
            assert config[k] == v, config
        assert_serial_port_configuration({p: p == port for p in ports})


def test_disabling_serial_port():
    ports = call('system.advanced.serial_port_choices')
    assert 'ttyS0' in ports, ports

    for port in ports:
        test_config = {'serialconsole': False, 'serialport': port}
        config = call('system.advanced.update', test_config)
        for k, v in test_config.items():
            assert config[k] == v, config
        assert_serial_port_configuration({p: False for p in ports})


def assert_serial_port_configuration(ports):
    for port, enabled in ports.items():
        is_enabled = ssh(f'systemctl is-enabled serial-getty@{port}.service', False).strip() == 'enabled'
        assert is_enabled is enabled, f'{port!r} enabled assertion failed: {is_enabled!r} != {enabled!r}'
        is_enabled = ssh(f'systemctl is-active --quiet serial-getty@{port}.service', False, True)['return_code'] == 0
        assert is_enabled is enabled, f'{port!r} active assertion failed: {is_enabled!r} != {enabled!r}'
