import pytest
import time

from pytest_dependency import depends
from functions import GET, PUT, wait_on_job
from auto_config import ha, pool_name, interface, ip
from middlewared.test.integration.utils import call


# Read all the test below only on non-HA
if not ha:
    def test_01_get_kubernetes_bindip_choices():
        results = GET('/kubernetes/bindip_choices/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert '0.0.0.0' in results.json(), results.text
        assert ip in results.json(), results.text

    @pytest.mark.dependency(name='setup_kubernetes')
    def test_02_setup_kubernetes(request):
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

    def test_06_kubernetes_config_acl(request):
        depends(request, ['setup_kubernetes'])
        acl_mode = call('filesystem.stat', '/etc/rancher/k3s/k3s.yaml')
        netdata_group = call('group.query', [['group', '=', 'netdata']], {'get': True})
        assert acl_mode['gid'] == netdata_group['gid']
        assert (acl_mode['mode'] & 0o640) == 0o640

    def test_07_kubernetes_pods_stats(request):
        depends(request, ['setup_kubernetes'])
        while True:
            time.sleep(5)
            kube_system_pods = call(
                'k8s.pod.query', [
                    ['metadata.namespace', '=', 'kube-system']
                ], {'select': ['metadata.name', 'status.phase']}
            )
            if any(pod['status']['phase'] == 'Running' for pod in kube_system_pods):
                break

        stats = call('chart.release.stats_internal', kube_system_pods)
        assert any(
            d[k] > 0 for d, k in (
                (stats, 'memory'), (stats, 'cpu'), (stats['network'], 'incoming'), (stats['network'], 'outgoing')
            )
        ), stats
