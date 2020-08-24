import os
import yaml


def render(middleware):
    config = middleware.call_sync('kubernetes.config')
    os.makedirs('/etc/rancher/k3s', exist_ok=True)
    with open('/etc/rancher/k3s', 'w') as f:
        f.write(yaml.dump({
            'cluster-cidr': config['cluster_cidr'],
            'service-cidr': config['service_cidr'],
            'cluster-dns': config['cluster_dns_ip'],
        }))
