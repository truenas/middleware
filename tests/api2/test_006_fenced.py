import pytest
import sys
from os import getcwd, environ
apifolder = getcwd()
sys.path.append(apifolder)

from functions import make_ws_request
from auto_config import ha, dev_test

pytestmark = pytest.mark.skipif(not ha or dev_test, reason='Only applicable to HA')
IP = environ.get('controller1_ip')
assert IP, 'Need controller 1 IP before this will work'


def test_01_verify_fenced_is_running(request):
    payload = {'msg': 'method', 'method': 'failover.fenced.run_info', 'params': []}
    res = make_ws_request(IP, payload)
    assert res['result']['running'], res
