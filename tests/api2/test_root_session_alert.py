import pytest

from middlewared.test.integration.assets.product import product_type
from middlewared.test.integration.utils.client import client, truenas_server
from middlewared.test.integration.utils import call
from time import sleep


@pytest.fixture(scope="function")
def set_product_type(request):
    # force SCALE_ENTERPRISE product type
    with product_type():
        yield


def get_session_alert(call_fn, session_id):
    # sleep a little while to let auth event get logged
    sleep(5)

    alert = call_fn('alert.run_source', 'AdminSession')
    assert alert

    assert session_id in alert[0]['args']['sessions'], str(alert[0]['args'])


def check_session_alert(call_fn):
    session_id = call_fn('auth.sessions', [['current', '=', True]], {'get': True})['id']
    get_session_alert(call_fn, session_id)


def test_root_session(set_product_type):
    # first check with our regular persistent session
    check_session_alert(call)

    with client(host_ip=truenas_server.ip) as c:
        # check that we also pick up second alert
        check_session_alert(c.call)
