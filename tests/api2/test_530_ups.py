#!/usr/bin/env python3
# License: BSD

import os
from tempfile import NamedTemporaryFile
from time import sleep

import pytest
from assets.websocket.service import ensure_service_enabled, ensure_service_started
from auto_config import password, user
from functions import send_file

from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server

DUMMY_FAKEDATA_DEV = '/tmp/fakedata.dev'
SHUTDOWN_MARKER_FILE = '/tmp/is_shutdown'

first_ups_list = [
    'rmonitor',
    'mode',
    'shutdown',
    'port',
    'remotehost',
    'identifier',
    'driver',
    'monpwd'
]

second_ups_list = [
    'rmonitor',
    'mode',
    'shutdown',
    'port',
    'identifier',
    'monpwd'
]

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


def remove_file(filepath):
    ssh(f'rm {filepath}', check=False)


def did_shutdown():
    return ssh(f'cat {SHUTDOWN_MARKER_FILE}', check=False) == "done\n"


def write_fake_data(data={}):
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
    del old_config['complete_identifier']
    del old_config['id']
    payload = {
        'mode': 'MASTER',
        'driver': 'dummy-ups',
        'port': DUMMY_FAKEDATA_DEV,
        'description': 'dummy-ups in dummy-once mode',
        'shutdowncmd': f'echo done > {SHUTDOWN_MARKER_FILE}'
    }
    call('ups.update', payload)
    try:
        yield
    finally:
        call('ups.update', old_config)
        remove_file(SHUTDOWN_MARKER_FILE)
        remove_file(DUMMY_FAKEDATA_DEV)


def test_01_get_ups_service_id():
    global ups_id
    results = call('service.query', [['service', '=', 'ups']], {'get': True})
    assert results['state'] == 'STOPPED', results
    assert results['enable'] is False, results
    ups_id = results['id']


def test_02_Enabling_UPS_Service_at_boot():
    call('service.update', 'ups', {'enable': True})


def test_03_look_if_UPS_service_is_enable():
    results = call('service.query', [['service', '=', 'ups']], {'get': True})
    assert results['enable'] is True, results


def test_04_Set_UPS_options():
    global payload, results
    payload = {
        'rmonitor': True,
        'mode': 'MASTER',
        'shutdown': 'BATT',
        'port': '655',
        'remotehost': '127.0.0.1',
        'identifier': 'ups',
        'driver': 'usbhid-ups$PROTECT NAS',
        'monpwd': 'mypassword'
    }
    results = call('ups.update', payload)


@pytest.mark.parametrize('data', first_ups_list)
def test_05_look_at_UPS_options_output_of_(data):
    assert payload[data] == results[data], results.text


def test_06_starting_ups_service():
    call('service.start', 'ups')


def test_07_look_UPS_service_status_is_running():
    results = call('service.query', [['service', '=', 'ups']], {'get': True})
    assert results['state'] == 'RUNNING', results


def test_08_get_API_reports_UPS_configuration_as_saved():
    global results
    results = call('ups.config')


@pytest.mark.parametrize('data', first_ups_list)
def test_09_look_API_reports_UPS_configuration_of_(data):
    assert payload[data] == results[data], results


def test_10_change_UPS_options_while_service_is_running():
    global payload, results
    payload = {
        'port': '65545',
        'identifier': 'boo'
    }
    results = call('ups.update', payload)


@pytest.mark.parametrize('data', ['port', 'identifier'])
def test_11_look_at_UPS_options_output_of_(data):
    assert payload[data] == results[data], results


def test_12_get_API_reports_UPS_configuration_as_saved():
    global results
    results = call('ups.config')


@pytest.mark.parametrize('data', ['port', 'identifier'])
def test_13_look_API_reports_UPS_configuration_of_(data):
    assert payload[data] == results[data], results.text


def test_14_look_if_UPS_service_status_is_still_running():
    results = call('service.query', [['service', '=', 'ups']], {'get': True})
    assert results['state'] == 'RUNNING', results.text


def test_15_stop_ups_service():
    call('service.stop', 'ups')


def test_16_look_UPS_service_status_is_stopped():
    results = call('service.query', [['service', '=', 'ups']], {'get': True})
    assert results['state'] == 'STOPPED', results


def test_17_Change_UPS_options():
    global payload, results
    payload = {
        'rmonitor': False,
        'mode': 'SLAVE',
        'shutdown': 'LOWBATT',
        'port': '65535',
        'identifier': 'foo',
        'monpwd': 'secondpassword'
    }
    results = call('ups.update', payload)


@pytest.mark.parametrize('data', second_ups_list)
def test_18_look_at_change_UPS_options_output_of_(data):
    assert payload[data] == results[data], results.text


def test_19_starting_ups_service():
    call('service.start', 'ups')


def test_20_look_UPS_service_status_is_running():
    results = call('service.query', [['service', '=', 'ups']], {'get': True})
    assert results['state'] == 'RUNNING', results


def test_21_get_API_reports_UPS_configuration_as_changed():
    global results
    results = call('ups.config')


@pytest.mark.parametrize('data', second_ups_list)
def test_22_look_API_reports_UPS_configuration_of_(data):
    assert payload[data] == results[data], results.text


def test_23_get_ups_driver_choice():
    results = call('ups.driver_choices')
    assert isinstance(results, dict) is True, results
    global ups_dc
    ups_dc = results


def test_24_get_ups_port_choice():
    results = call('ups.port_choices')
    assert isinstance(results, list) is True, results
    assert isinstance(results[0], str) is True, results


def test_25_Disabling_UPS_Service():
    call('service.update', 'ups', {'enable': False})


def test_26_Disabling_UPS_Service_at_boot():
    results = call('service.query', [['id', '=', ups_id]], {'get': True})
    assert results['enable'] is False, results


def test_27_stop_ups_service():
    call('service.stop', 'ups')


def test_28_look_UPS_service_status_is_stopped():
    results = call('service.query', [['id', '=', ups_id]], {'get': True})
    assert results['state'] == 'STOPPED', results


def test_29_ups_online_to_online_lowbattery(ups_running, dummy_ups_driver_configured):
    sleep(2)
    assert 'UPSBatteryLow' not in [alert['klass'] for alert in call('alert.list')]
    write_fake_data({'battery.charge': 20, 'ups.status': 'OL LB'})
    alert = wait_for_alert('UPSBatteryLow')
    assert alert
    assert 'battery.charge: 20' in alert['formatted'], alert
    assert not did_shutdown()


def test_30_ups_online_to_onbatt(ups_running, dummy_ups_driver_configured):
    assert 'UPSOnBattery' not in [alert['klass'] for alert in call('alert.list')]
    write_fake_data({'battery.charge': 40, 'ups.status': 'OB'})
    alert = wait_for_alert('UPSOnBattery')
    assert alert
    assert 'battery.charge: 40' in alert['formatted'], alert
    assert not did_shutdown()


def test_31_ups_onbatt_to_online(ups_running, dummy_ups_driver_configured):
    assert 'UPSOnline' not in [alert['klass'] for alert in call('alert.list')]
    write_fake_data({'battery.charge': 100, 'ups.status': 'OL'})
    alert = wait_for_alert('UPSOnline')
    assert alert
    assert 'battery.charge: 100' in alert['formatted'], alert
    assert not did_shutdown()


def test_32_ups_online_to_onbatt_lowbattery(ups_running, dummy_ups_driver_configured):
    assert 'UPSOnBattery' not in [alert['klass'] for alert in call('alert.list')]
    write_fake_data({'battery.charge': 10, 'ups.status': 'OB LB'})
    alert = wait_for_alert('UPSOnBattery')
    assert alert
    assert 'battery.charge: 10' in alert['formatted'], alert
    alert = wait_for_alert('UPSBatteryLow')
    assert alert
    assert 'battery.charge: 10' in alert['formatted'], alert
    assert did_shutdown()
