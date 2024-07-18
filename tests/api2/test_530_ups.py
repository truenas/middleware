#!/usr/bin/env python3
# License: BSD

import pytest

from middlewared.test.integration.utils import call

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
