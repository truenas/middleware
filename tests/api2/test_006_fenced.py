import pytest
import sys
from pytest_dependency import depends
from os import getcwd, environ
apifolder = getcwd()
sys.path.append(apifolder)

from functions import make_ws_request
from auto_config import ha, dev_test

pytestmark = pytest.mark.skipif(not ha or dev_test, reason='Only applicable to HA')
IP = environ.get('controller1_ip')
assert IP, 'Need controller 1 IP before this will work'


@pytest.mark.dependency(name='FORCE_START_FENCED')
def test_01_force_start_fenced():
    payload = {'msg': 'method', 'method': 'failover.fenced.start', 'params': [True]}
    res = make_ws_request(IP, payload)
    assert res['result'] == 0, res


def test_02_verify_fenced_is_running(request):
    depends(request, ['FORCE_START_FENCED'])
    payload = {'msg': 'method', 'method': 'failover.fenced.run_info', 'params': []}
    res = make_ws_request(IP, payload)
    assert res['result']['running'], res
