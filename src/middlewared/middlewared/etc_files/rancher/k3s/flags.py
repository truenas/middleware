import ipaddress
import os
import yaml


def render(service, middleware):
    config = middleware.call_sync('kubernetes.config')
    kube_controller_args = f'node-cidr-mask-size={ipaddress.ip_network(config["cluster_cidr"]).prefixlen}'
    os.makedirs('/etc/rancher/k3s', exist_ok=True)
    with open('/etc/rancher/k3s/flags.yaml', 'w') as f:
        f.write(yaml.dump({
            'cluster-cidr': config['cluster_cidr'],
            'service-cidr': config['service_cidr'],
            'cluster-dns': config['cluster_dns_ip'],
            'data-dir': os.path.join('/mnt', config['dataset'], 'k3s'),
            'kube-controller-manager-arg': kube_controller_args,
        }))
