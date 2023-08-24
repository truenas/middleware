import contextlib
import ipaddress
import json
import os
import shutil
import yaml


FLAGS_PATH = '/etc/rancher/k3s/config.yaml'
KUBELET_CONFIG_PATH = '/etc/rancher/k3s/kubelet_config.yaml'


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
        'enable-admission-plugins=NodeRestriction,NamespaceLifecycle,ServiceAccount',
        'audit-log-path=/var/log/k3s_server_audit.log',
        'audit-log-maxage=30',
        'audit-log-maxbackup=10',
        'audit-log-maxsize=100',
        'service-account-lookup=true',
        'feature-gates=MixedProtocolLBService=true',
    ]
    kubelet_args = [
        f'config={KUBELET_CONFIG_PATH}',
    ]
    os.makedirs('/etc/rancher/k3s', exist_ok=True)

    features_mapping = {'servicelb': 'servicelb', 'metrics_server': 'metrics-server'}

    with open(KUBELET_CONFIG_PATH, 'w') as f:
        f.write(yaml.dump({
            'apiVersion': 'kubelet.config.k8s.io/v1beta1',
            'kind': 'KubeletConfiguration',
            'maxPods': 250,
            'shutdownGracePeriod': '15s',
            'shutdownGracePeriodCriticalPods': '10s',
        }))

    with open(FLAGS_PATH, 'w') as f:
        f.write(yaml.dump({
            'cluster-cidr': config['cluster_cidr'],
            'service-cidr': config['service_cidr'],
            'cluster-dns': config['cluster_dns_ip'],
            'data-dir': os.path.join('/mnt', config['dataset'], 'k3s'),
            'node-ip': config['node_ip'],
            'node-external-ip': ','.join([
                interface['address'] for interface in middleware.call_sync('interface.ip_in_use', {'ipv6': False})
            ]),
            'kube-controller-manager-arg': kube_controller_args,
            'kube-apiserver-arg': kube_api_server_args,
            'kubelet-arg': kubelet_args,
            'protect-kernel-defaults': True,
            'disable': [features_mapping[feature] for feature in features_mapping if not config[feature]],
            'write-kubeconfig-mode': 644,
        }))

    with open('/etc/containerd.json', 'w') as f:
        f.write(json.dumps({
            'appsDataset': config['dataset'],
        }))
