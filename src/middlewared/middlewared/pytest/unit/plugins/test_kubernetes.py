import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.pytest.unit.helpers import load_compound_service
from middlewared.pytest.unit.middleware import Middleware


KubernetesService = load_compound_service('kubernetes')


@pytest.mark.parametrize('ha_capable,license_features,should_work', [
    (True, [], False),
    (True, ['JAILS'], True),
    (False, [], True),
])
@pytest.mark.asyncio
async def test_kubernetes_configuration_for_licensed_and_unlicensed_systems(ha_capable, license_features, should_work):
    m = Middleware()
    k8s_svc = KubernetesService(m)
    k8s_settings = {
        'pool': 'pool',
        'cluster_cidr': '172.16.0.0/16',
        'service_cidr': '172.17.0.0/16',
        'cluster_dns_ip': '172.17.0.10',
        'route_v4_interface': None,
        'route_v4_gateway': None,
        'route_v6_interface': None,
        'route_v6_gateway': None,
        'node_ip': '0.0.0.0',
        'configure_gpus': True,
        'servicelb': True,
        'validate_host_path': True,
    }

    m['interface.choices'] = lambda *args: []
    m['interface.ip_in_use'] = lambda *args: [{
        'type': 'INET',
        'address': '0.0.0.0',
        'netmask': 0,
        'broadcast': '255.255.255.255'
    }]
    m['interface.query'] = lambda *args: []
    m['pool.query'] = lambda *args: [{'name': 'pool'}]
    m['route.configured_default_ipv4_route'] = lambda *args: '192.168.0.1'
    m['system.is_ha_capable'] = lambda *args: ha_capable
    m['system.license'] = lambda *args: {'features': license_features}
    m['kubernetes.check_config_on_apps_dataset'] = lambda *args: None

    k8s_schema = 'kubernetes_update'
    if should_work:
        assert await k8s_svc.validate_data(k8s_settings, k8s_schema, k8s_settings) is None
    else:
        with pytest.raises(ValidationErrors) as verrors:
            await k8s_svc.validate_data(k8s_settings, k8s_schema, k8s_settings)

        assert [e.errmsg for e in verrors.value.errors] == ['System is not licensed to use Applications']
