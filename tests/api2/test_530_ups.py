import os
from tempfile import NamedTemporaryFile
from time import sleep

import pytest

from assets.websocket.service import ensure_service_enabled, ensure_service_started
from auto_config import password, user

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import unprivileged_user_client
from middlewared.test.integration.utils import call, mock, ssh
from middlewared.test.integration.utils.alert import wait_for_alerts_by_class
from middlewared.test.integration.utils.client import truenas_server
from middlewared.test.integration.utils.legacy_functions import send_file

DUMMY_FAKEDATA_DEV = '/tmp/fakedata.dev'
SHUTDOWN_MARKER_FILE = '/tmp/is_shutdown'
# `upsmon` reports lost communication as soon as it starts and arms a 10 second COMMBAD timer. Its
# own poll frequency decides when the driver cancels that timer.
UPSMON_POLLFREQ = 5
# `doshutdown` sleeps this long before it runs `SHUTDOWNCMD`. The generated `upsmon.conf` leaves
# `FINALDELAY` at the NUT default.
UPSMON_FINALDELAY = 5

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


def ups_alert_classes():
    return sorted(alert['klass'] for alert in call('alert.list') if alert['klass'].startswith('UPS'))


def clear_ups_alerts():
    call('ups.dismiss_alerts')
    for _ in range(30):
        if not ups_alert_classes():
            return
        sleep(1)

    raise AssertionError(f'UPS alerts were not dismissed: {ups_alert_classes()}')


def upsc():
    """The driver's view of the data, with the `upsc` errors kept for the assertion messages."""
    return ssh(f'upsc {call("ups.config")["complete_identifier"]} 2>&1', check=False)


def normalize_variables(variables):
    """Make `upsc` output comparable to the data a test published.

    `ups.status` is a set of flags, so neither flag order nor a substring of that line means
    anything. A set comparison also exposes the `FSD` flag that `upsd` prepends.
    """
    normalized = {key: str(value) for key, value in variables.items()}
    if 'ups.status' in normalized:
        normalized['ups.status'] = frozenset(normalized['ups.status'].split())

    return normalized


def served_variables(served):
    variables = {}
    for line in served.splitlines():
        key, separator, value = line.partition(': ')
        if separator:
            variables[key] = value

    return normalize_variables(variables)


def assert_no_forced_shutdown():
    """`upsd` records the forced shutdown as soon as `upsmon` declares it. `SHUTDOWNCMD` only runs
    seconds later, so the flag is the early and reliable half of the same event."""
    assert 'FSD' not in served_variables(upsc()).get('ups.status', frozenset())
    assert not did_shutdown()


def wait_for_shutdown():
    """Wait for `SHUTDOWNCMD` to run.

    `upsmon` declares the forced shutdown at once, then waits up to `HOSTSYNC` seconds for
    secondaries to log out and sleeps `FINALDELAY` more. So the marker file lags the low battery
    alert by several seconds.
    """
    timeout = call('ups.config')['hostsync'] + UPSMON_FINALDELAY + 10
    for _ in range(timeout):
        if did_shutdown():
            return
        sleep(1)

    raise AssertionError(
        f'`upsmon` did not run the shutdown command in {timeout} seconds. A missing `FSD` flag '
        f'means it never declared the shutdown: {upsc()}'
    )


def write_fake_data(data=None):
    data = data or {}
    all_data = default_dummy_data | data
    with NamedTemporaryFile() as f:
        for k, v in all_data.items():
            f.write(f'{k}: {v}\n'.encode('utf-8'))
        f.flush()
        os.fchmod(f.fileno(), 0o644)
        results = send_file(f.name, f'{DUMMY_FAKEDATA_DEV}.new', user, password, truenas_server.ip)
        assert results['result'], str(results['output'])

    # `scp` truncates the destination and then writes it. The driver polls once a second, so it can
    # read a half-written file. A rename is atomic, so the driver only ever sees a complete file.
    ssh(f'mv {DUMMY_FAKEDATA_DEV}.new {DUMMY_FAKEDATA_DEV}')


def publish_fake_data(data, forced_shutdown=False):
    """Write `data` and wait for the dummy driver to serve it.

    `dummy-ups` in dummy-once mode re-reads its file only when the whole second of the file mtime
    differs from the one it read last. A write in that same second is invisible forever, so `touch`
    the file until the new values appear.

    Pass `forced_shutdown` for data that makes `upsmon` shut the system down. Anywhere else the
    `FSD` flag means an earlier shutdown killed `upsmon`, so no further event can ever fire.
    """
    write_fake_data(data)
    expected = normalize_variables(data)
    for _ in range(30):
        served = upsc()
        variables = served_variables(served)
        flags = variables.get('ups.status', frozenset())
        assert forced_shutdown or 'FSD' not in flags, (
            f'`upsd` has the forced shutdown flag set, and keeps it until it restarts: {served}'
        )
        # `FSD` is the flag `upsd` prepends, never one the driver read from the data file.
        if 'ups.status' in variables:
            variables['ups.status'] = flags - {'FSD'}
        if all(variables.get(key) == value for key, value in expected.items()):
            return
        ssh(f'touch {DUMMY_FAKEDATA_DEV}')
        sleep(1)

    raise AssertionError(f'The driver does not serve {data}: {served}')


def wait_for_dummy_driver():
    """Wait for `upsd` to serve the driver, then clear what the start-up produced.

    A driver that takes more than 10 seconds to connect leaves a `UPSCommbad` alert from the
    COMMBAD timer, and `upsmon` also reports NOCOMM while `upsd` is not listening yet.
    """
    for _ in range(30):
        if 'ups.status' in served_variables(upsc()):
            break
        sleep(1)
    else:
        raise AssertionError(f'The dummy driver did not start: {upsc()}')

    sleep(UPSMON_POLLFREQ + 1)
    clear_ups_alerts()


@pytest.fixture(scope='module')
def ups_running():
    with ensure_service_enabled('ups'):
        with ensure_service_started('ups'):
            yield


@pytest.fixture()
def dummy_ups_driver_configured():
    """Give every test its own UPS service.

    A test that reaches a forced shutdown leaves the `FSD` flag on `upsd` and no running `upsmon`.
    Only a restart of the service clears either, so a shared service would fail every later test.
    """
    write_fake_data()
    remove_file(SHUTDOWN_MARKER_FILE)
    old_config = call('ups.config')
    # Exclude fields that can't be passed to ups.update
    old_config_dict = {k: v for k, v in old_config.items() if k not in ('complete_identifier', 'id')}

    # Stop the service before reconfiguring to avoid _service_change
    # trying to restart with the old (hardware-dependent) driver config.
    call('service.control', 'STOP', 'ups', job=True)

    # Every field these tests depend on is set here, because the preceding tests in this module
    # leave a different configuration behind. `shutdown` decides whether LOWBATT runs the shutdown
    # command, and `upsmon` does not start at all without a password.
    payload = {
        'mode': 'MASTER',
        'driver': 'dummy-ups',
        'port': DUMMY_FAKEDATA_DEV,
        'description': 'dummy-ups in dummy-once mode',
        'shutdown': 'LOWBATT',
        'monpwd': 'dummypassword',
        'shutdowncmd': f'echo done > {SHUTDOWN_MARKER_FILE}'
    }
    with mock('ups.driver_choices', return_value={'dummy-ups': 'Driver for multi-purpose UPS emulation',
                                                  'usbhid-ups$PROTECT NAS': 'AEG Power Solutions ups 3 PROTECT NAS (usbhid-ups)'}):
        call('ups.update', payload)
        # Start fresh with the dummy-ups config
        call('service.control', 'START', 'ups', {'silent': False}, job=True)
        try:
            wait_for_dummy_driver()
            yield
        finally:
            call('service.control', 'STOP', 'ups', job=True)
            # These alerts are never deleted automatically, so they would stay for the whole run.
            clear_ups_alerts()
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
    publish_fake_data({'battery.charge': 20, 'ups.status': 'OL LB'})
    alerts = wait_for_alerts_by_class('UPSBatteryLow')
    assert alerts
    assert 'battery.charge: 20' in alerts[0]['formatted'], alerts
    assert ups_alert_classes() == ['UPSBatteryLow']
    assert_no_forced_shutdown()


def test__ups_online_to_onbatt(ups_running, dummy_ups_driver_configured):
    publish_fake_data({'battery.charge': 40, 'ups.status': 'OB'})
    alerts = wait_for_alerts_by_class('UPSOnBattery')
    assert alerts
    assert 'battery.charge: 40' in alerts[0]['formatted'], alerts
    assert ups_alert_classes() == ['UPSOnBattery']
    assert_no_forced_shutdown()


def test__ups_onbatt_to_online(ups_running, dummy_ups_driver_configured):
    # The driver starts online, so this test puts the UPS on battery itself. `upsmon` only reports
    # a transition it polled, so the on battery alert must arrive before the UPS goes back online.
    publish_fake_data({'battery.charge': 40, 'ups.status': 'OB'})
    assert wait_for_alerts_by_class('UPSOnBattery')
    publish_fake_data({'battery.charge': 100, 'ups.status': 'OL'})
    alerts = wait_for_alerts_by_class('UPSOnline')
    assert alerts
    assert 'battery.charge: 100' in alerts[0]['formatted'], alerts
    assert ups_alert_classes() == ['UPSOnline']
    assert_no_forced_shutdown()


def test__ups_online_to_onbatt_lowbattery(ups_running, dummy_ups_driver_configured):
    publish_fake_data({'battery.charge': 90, 'ups.status': 'OB'})
    alerts = wait_for_alerts_by_class('UPSOnBattery')
    assert alerts
    assert 'battery.charge: 90' in alerts[0]['formatted'], alerts
    publish_fake_data({'battery.charge': 10, 'ups.status': 'OB LB'}, forced_shutdown=True)
    alerts = wait_for_alerts_by_class('UPSBatteryLow')
    assert alerts
    assert 'battery.charge: 10' in alerts[0]['formatted'], alerts
    # The simultaneous SHUTDOWN event carries no alert of its own, so the low battery alert stays.
    assert ups_alert_classes() == ['UPSBatteryLow']
    wait_for_shutdown()


def test__pass_through_fields_may_only_be_changed_by_a_full_admin():
    """These land verbatim in the NUT config; `shutdowncmd` is what upsmon runs as root (NAS-142160).

    All four are sent in one call because every offending field is reported at once.
    """
    fields = {
        'shutdowncmd': '/bin/sh -c id',
        'options': 'user = root',
        'optionsupsd': 'LISTEN 0.0.0.0 3493',
        'extrausers': '[hax]\n\tpassword = hax\n\tupsmon master',
    }
    with unprivileged_user_client(['SYSTEM_GENERAL_WRITE']) as c:
        with pytest.raises(ValidationErrors) as ve:
            c.call('ups.update', fields)

    assert {error.attribute for error in ve.value.errors} == {f'data.{field}' for field in fields}
