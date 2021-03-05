import os
import pytest
import sys
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, PUT, wait_on_job
from auto_config import ha, scale, pool_name, interface, ip, dev_test

if dev_test:
    reason = 'Skip for testing'
else:
    reason = 'Skipping test for HA' if ha else 'Skipping test for CORE'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(ha or not scale or dev_test, reason=reason)


def test_01_get_kubernetes_bindip_choices():
    results = GET('/kubernetes/bindip_choices/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert '0.0.0.0' in results.json(), results.text
    assert ip in results.json(), results.text


@pytest.mark.dependency(name='setup_kubernetes')
def test_02_setup_kubernetes(request):
    depends(request, ["pool_04"], scope="session")
    global payload
    gateway = GET("/network/general/summary/").json()['default_routes'][0]
    payload = {
        'pool': pool_name,
        'route_v4_interface': interface,
        'route_v4_gateway': gateway,
        'node_ip': ip
    }
    results = PUT('/kubernetes/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@pytest.mark.parametrize('data', ['pool', 'route_v4_interface', 'route_v4_gateway', 'node_ip'])
def test_03_verify_kubernetes(request, data):
    depends(request, ["setup_kubernetes"])
    results = GET('/kubernetes/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()[data] == payload[data], results.text


def test_04_get_kubernetes_node_ip(request):
    depends(request, ["setup_kubernetes"])
    results = GET('/kubernetes/node_ip/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), str), results.text
    assert results.json() == ip, results.text


def test_05_get_kubernetes_events(request):
    depends(request, ["setup_kubernetes"])
    results = GET('/kubernetes/events/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
