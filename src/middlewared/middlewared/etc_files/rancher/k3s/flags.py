import os
import yaml


def render(service, middleware):
    config = middleware.call_sync('kubernetes.config')
    os.makedirs('/etc/rancher/k3s', exist_ok=True)
    with open('/etc/rancher/k3s/flags.conf', 'w') as f:
        f.write(yaml.dump({
            'cluster-cidr': config['cluster_cidr'],
            'service-cidr': config['service_cidr'],
            'cluster-dns': config['cluster_dns_ip'],
            'data-dir': os.path.join('/mnt', config['dataset'], 'k3s'),
        }))
