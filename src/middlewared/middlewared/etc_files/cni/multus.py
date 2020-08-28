import os
import json


def render(service, middleware):
    config = middleware.call_sync('kubernetes.config')
    if not middleware.call_sync('k8s.cni.validate_cni_integrity', 'multus', config):
        return

    os.makedirs('/etc/cni/net.d/multus.d', exist_ok=True)

    with open('/etc/cni/net.d/00-multus.conf', 'w') as f:
        f.write(json.dumps({
            'cniVersion': '0.3.1',
            'name': 'multus-cni-network',
            'type': 'multus',
            'logLevel': 'debug',
            'LogFile': '/var/log/multus.log',
            'kubeconfig': '/etc/cni/net.d/multus.d/multus.kubeconfig',
            'delegates': [middleware.call_sync('k8s.cni.kube_router_config')]
        }))
