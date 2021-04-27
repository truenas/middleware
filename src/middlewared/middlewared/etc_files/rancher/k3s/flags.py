import contextlib
import ipaddress
import os
import shutil
import yaml


FLAGS_PATH = '/etc/rancher/k3s/config.yaml'


def render(service, middleware):
    shutil.rmtree('/etc/cni/net.d', ignore_errors=True)
    config = middleware.call_sync('kubernetes.config')
    if not config['pool']:
        with contextlib.suppress(OSError):
            os.unlink(FLAGS_PATH)
        return

    kube_controller_args = [
        f'node-cidr-mask-size={ipaddress.ip_network(config["cluster_cidr"]).prefixlen}',
        'terminated-pod-gc-threshold=5',
    ]
    kube_api_server_args = [
        'service-node-port-range=9000-65535',
        'enable-admission-plugins=NodeRestriction,NamespaceLifecycle,ServiceAccount,AlwaysPullImages',
        'audit-log-path=/var/log/k3s_server_audit.log',
        'audit-log-maxage=30',
        'audit-log-maxbackup=10',
        'audit-log-maxsize=100',
        'service-account-lookup=true',
    ]
    os.makedirs('/etc/rancher/k3s', exist_ok=True)
    with open(FLAGS_PATH, 'w') as f:
        f.write(yaml.dump({
            'cluster-cidr': config['cluster_cidr'],
            'service-cidr': config['service_cidr'],
            'cluster-dns': config['cluster_dns_ip'],
            'data-dir': os.path.join('/mnt', config['dataset'], 'k3s'),
            'kube-controller-manager-arg': kube_controller_args,
            'node-ip': config['node_ip'],
            'kube-apiserver-arg': kube_api_server_args,
            'protect-kernel-defaults': True,
        }))
