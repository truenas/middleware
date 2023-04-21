import sys
from os import getcwd, environ
apifolder = getcwd()
sys.path.append(apifolder)

from functions import make_ws_request
from auto_config import ha

# Do not run the code code below on non-HA
if ha:
    IP = environ.get('controller1_ip')
    assert IP, 'Need controller 1 IP before this will work'

    def test_01_verify_fenced_is_running(request):
        payload = {'msg': 'method', 'method': 'failover.fenced.run_info', 'params': []}
        res = make_ws_request(IP, payload)
        assert res['result']['running'], res
