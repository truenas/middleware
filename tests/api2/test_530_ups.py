import os
from tempfile import NamedTemporaryFile
from time import sleep

import pytest

from assets.websocket.service import ensure_service_enabled, ensure_service_started
from auto_config import password, user
from functions import send_file

from middlewared.test.integration.utils import call, mock, ssh
from middlewared.test.integration.utils.client import truenas_server

DUMMY_FAKEDATA_DEV = '/tmp/fakedata.dev'
SHUTDOWN_MARKER_FILE = '/tmp/is_shutdown'

first_ups_payload = {
    'rmonitor': True,
    'mode': 'MASTER',
    'shutdown': 'BATT',
    'port': '655',
    'remotehost': '127.0.0.1',
    'identifier': 'ups',
    'driver': 'usbhid-ups$PROTECT NAS',
    'monpwd': 'mypassword'
}

second_ups_payload = {
    'rmonitor': False,
    'mode': 'SLAVE',
    'shutdown': 'LOWBATT',
    'port': '65535',
    'identifier': 'foo',
    'monpwd': 'secondpassword'
}

default_dummy_data = {
    'battery.charge': 100,
    'driver.parameter.pollinterval': 2,
    'input.frequency': 49.9,
    'input.frequency.nominal': 50.0,
    'input.voltage': 230,
    'input.voltage.nominal': 240,
    'ups.status': 'OL',
    'ups.timer.shutdown': -1,
    'ups.timer.start': -1,
}


def get_service_state():
    return call('service.query', [['service', '=', 'ups']], {'get': True})


def remove_file(filepath):
    ssh(f'rm {filepath}', check=False)


def did_shutdown():
    return ssh(f'cat {SHUTDOWN_MARKER_FILE}', check=False) == "done\n"


def write_fake_data(data=None):
    data = data or {}
    all_data = default_dummy_data | data
    with NamedTemporaryFile() as f:
        for k, v in all_data.items():
            f.write(f'{k}: {v}\n'.encode('utf-8'))
        f.flush()
        os.fchmod(f.fileno(), 0o644)
        results = send_file(f.name, DUMMY_FAKEDATA_DEV, user, password, truenas_server.ip)
        assert results['result'], str(results['output'])


def wait_for_alert(klass, retries=10):
    assert retries > 0
    while retries:
        alerts = call('alert.list')
        for alert in alerts:
            if alert['klass'] == klass:
                return alert
        sleep(1)
        retries -= 1


@pytest.fixture(scope='module')
def ups_running():
    with ensure_service_enabled('ups'):
        with ensure_service_started('ups'):
            yield


@pytest.fixture(scope='module')
def dummy_ups_driver_configured():
    write_fake_data()
    remove_file(SHUTDOWN_MARKER_FILE)
    old_config = call('ups.config')
    # Exclude fields that can't be passed to ups.update
    old_config_dict = {k: v for k, v in old_config.items() if k not in ('complete_identifier', 'id')}
    payload = {
        'mode': 'MASTER',
        'driver': 'dummy-ups',
        'port': DUMMY_FAKEDATA_DEV,
        'description': 'dummy-ups in dummy-once mode',
        'shutdowncmd': f'echo done > {SHUTDOWN_MARKER_FILE}'
    }
    with mock('ups.driver_choices', return_value={'dummy-ups': 'Driver for multi-purpose UPS emulation',
                                                  'usbhid-ups$PROTECT NAS': 'AEG Power Solutions ups 3 PROTECT NAS (usbhid-ups)'}):
        call('ups.update', payload)
        try:
            yield
        finally:
            # Reuse the same mock for teardown (don't create a nested mock!)
            call('ups.update', old_config_dict)
            remove_file(SHUTDOWN_MARKER_FILE)
            remove_file(DUMMY_FAKEDATA_DEV)


def test__enable_ups_service():
    results = get_service_state()
    assert results['state'] == 'STOPPED', results
    assert results['enable'] is False, results
    call('service.update', 'ups', {'enable': True})
    results = get_service_state()
    assert results['enable'] is True, results


def test__set_ups_options():
    results = call('ups.update', first_ups_payload)
    for data in first_ups_payload.keys():
        assert first_ups_payload[data] == results[data], results


def test__start_ups_service():
    call('service.control', 'START', 'ups', job=True)
    results = get_service_state()
    assert results['state'] == 'RUNNING', results


def test__get_reports_configuration_as_saved():
    results = call('ups.config')
    for data in first_ups_payload.keys():
        assert first_ups_payload[data] == results[data], results


def test__change_ups_options_while_service_is_running():
    payload = {
        'port': '65545',
        'identifier': 'boo'
    }
    results = call('ups.update', payload)
    for data in ['port', 'identifier']:
        assert payload[data] == results[data], results
    results = call('ups.config')
    for data in ['port', 'identifier']:
        assert payload[data] == results[data], results


def test__stop_ups_service():
    results = get_service_state()
    assert results['state'] == 'RUNNING', results
    call('service.control', 'STOP', 'ups', job=True)
    results = get_service_state()
    assert results['state'] == 'STOPPED', results


def test__change_ups_options():
    results = call('ups.update', second_ups_payload)
    for data in second_ups_payload.keys():
        assert second_ups_payload[data] == results[data], results
    call('service.control', 'START', 'ups', job=True)
    results = get_service_state()
    assert results['state'] == 'RUNNING', results
    results = call('ups.config')
    for data in second_ups_payload.keys():
        assert second_ups_payload[data] == results[data], results


def test__get_ups_driver_choice():
    results = call('ups.driver_choices')
    assert isinstance(results, dict) is True, results


def test__get_ups_port_choice():
    results = call('ups.port_choices')
    assert isinstance(results, list) is True, results
    assert isinstance(results[0], str) is True, results


def test__disable_and_stop_ups_service():
    call('service.update', 'ups', {'enable': False})
    results = get_service_state()
    assert results['enable'] is False, results
    call('service.control', 'STOP', 'ups', job=True)
    results = get_service_state()
    assert results['state'] == 'STOPPED', results


def test__ups_online_to_online_lowbattery(ups_running, dummy_ups_driver_configured):
    results = get_service_state()
    assert results['state'] == 'RUNNING', results
    sleep(2)
    assert 'UPSBatteryLow' not in [alert['klass'] for alert in call('alert.list')]
    write_fake_data({'battery.charge': 20, 'ups.status': 'OL LB'})
    alert = wait_for_alert('UPSBatteryLow')
    assert alert
    assert 'battery.charge: 20' in alert['formatted'], alert
    assert not did_shutdown()


def test__ups_online_to_onbatt(ups_running, dummy_ups_driver_configured):
    assert 'UPSOnBattery' not in [alert['klass'] for alert in call('alert.list')]
    write_fake_data({'battery.charge': 40, 'ups.status': 'OB'})
    alert = wait_for_alert('UPSOnBattery')
    assert alert
    assert 'battery.charge: 40' in alert['formatted'], alert
    assert not did_shutdown()


def test__ups_onbatt_to_online(ups_running, dummy_ups_driver_configured):
    assert 'UPSOnline' not in [alert['klass'] for alert in call('alert.list')]
    write_fake_data({'battery.charge': 100, 'ups.status': 'OL'})
    alert = wait_for_alert('UPSOnline')
    assert alert
    assert 'battery.charge: 100' in alert['formatted'], alert
    assert not did_shutdown()


def test__ups_online_to_onbatt_lowbattery(ups_running, dummy_ups_driver_configured):
    assert 'UPSOnBattery' not in [alert['klass'] for alert in call('alert.list')]
    write_fake_data({'battery.charge': 90, 'ups.status': 'OB'})
    alert = wait_for_alert('UPSOnBattery')
    assert alert
    assert 'battery.charge: 90' in alert['formatted'], alert
    write_fake_data({'battery.charge': 10, 'ups.status': 'OB LB'})
    alert = wait_for_alert('UPSBatteryLow')
    assert alert
    assert 'battery.charge: 10' in alert['formatted'], alert
    assert did_shutdown()
