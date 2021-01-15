import os


def render(service, middleware):
    k8s_config = middleware.call_sync('kubernetes.config')
    if not k8s_config['dataset']:
        return

    os.makedirs('/etc/rancher/node', exist_ok=True)
    with open('/etc/rancher/node/password', 'w') as f:
        f.write(middleware.call_sync('k8s.node.worker_node_password'))
