import os
import json


def render(service, middleware):
    if not middleware.call_sync('k8s.cni.validate_cni_integrity', 'multus'):
        return

    os.makedirs('/etc/cni/net.d/multus.d', exist_ok=True)

    with open('/etc/cni/net.d/00-multus.conf', 'w') as f:
        f.write(json.dumps({
            'cniVersion': '0.3.1',
            'name': 'multus-cni-network',
            'type': 'multus',
            'logLevel': 'error',
            'LogFile': '/var/log/multus.log',
            'kubeconfig': '/etc/cni/net.d/multus.d/multus.kubeconfig',
            'delegates': [middleware.call_sync('k8s.cni.kube_router_config')]
        }))
