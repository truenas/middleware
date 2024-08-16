import pytest

from middlewared.test.integration.utils.client import client, truenas_server
from middlewared.test.integration.utils import call


def get_session_alert(call_fn, session_id):
    alerts = call_fn('alert.list')
    alert_msg = None

    for alert in alerts:
        if alert['klass'] == 'AdminSessionActive':
            if session_id and session_id not in alert['formatted']:
                continue

            alert_msg = alert['formatted']
            break

    assert alert_msg is not None, str(alerts)
    return alert_msg


def check_session_alert(call_fn):
    session_id = call_fn('auth.sessions', [['current', '=', True]], {'get': True})['id']
    session_alert = get_session_alert(call_fn, session_id)

    return session_id


def test_root_session_alert():
    # We have a persistent root session so we expect alert to be present
    check_session_alert(call)


def test_root_session_logout():
    with client(host_ip=truenas_server.ip) as c:
        # ensure that client generates alert
        session_id = check_session_alert(c.call)
        c.call('auth.logout')

    # Make sure our session properly closed
    closed_session = call('auth.sessions', [['id', '=', session_id]])
    assert not closed_session

    # Make sure old session ID no longer in alert
    session_alert = get_session_alert(call, None)

    assert session_id not in session_alert
