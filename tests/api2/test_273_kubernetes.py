import os
import pytest
import sys
# from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, PUT, wait_on_job
from auto_config import ha, scale, pool_name, interface

reason = 'Skipping test for HA' if ha else 'Skipping test for CORE'
pytestmark = pytest.mark.skipif(ha or not scale, reason=reason)


def test_01_get_kubernetes_bindip_choices():
    results = GET('/kubernetes/bindip_choices/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['0.0.0.0'], results.text


def test_03_setup_kubernetes(request):
    global payload
    gateway = GET("/network/general/summary/").json()['default_routes'][0]
    payload = {
        'pool': pool_name,
        'route_v4_interface': interface,
        'route_v4_gateway': gateway,
        'node_ip': '0.0.0.0'
    }
    results = PUT('/kubernetes/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@pytest.mark.parametrize('data', ['pool', 'route_v4_interface', 'route_v4_gateway', 'node_ip'])
def test_02_verify_kubernetes(data):
    results = GET('/kubernetes/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()[data] == payload[data], results.text
