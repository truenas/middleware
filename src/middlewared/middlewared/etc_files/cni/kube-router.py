import json
import os
import yaml


def render(service, middleware):
    config = middleware.call_sync('kubernetes.config')
    os.makedirs('/etc/cni/net.d/kube-router.d', exist_ok=True)
    write_kube_router_conf(config, middleware)
    write_kube_router_kubeconfig(config)


def write_kube_router_conf(config, middleware):
    with open('/etc/cni/net.d/10-kuberouter.conflist', 'w') as f:
        f.write(json.dumps(middleware.call_sync('k8s.cni.kube_router_config')))


def write_kube_router_kubeconfig(config):
    with open('/etc/cni/net.d/kube-router.d/kubeconfig', 'w') as f:
        f.write(yaml.dump({
            'apiVersion': 'v1',
            'kind': 'Config',
            'clusterCIDR': config['cluster_cidr'],
            'clusters': [{
                'name': 'cluster',
                'cluster': {
                    'certificate-authority': '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt',
                    'server': 'https://127.0.0.1:6443',
                }
            }],
            'users': [{
                'name': 'kube-router',
                'user': {
                    'tokenFile': '/var/run/secrets/kubernetes.io/serviceaccount/token',
                }
            }],
            'contexts': [{
                'context': {
                    'cluster': 'cluster',
                    'user': 'kube-router',
                },
                'name': 'kube-router-context'
            }],
            'current-context': 'kube-router-context',
        }))
