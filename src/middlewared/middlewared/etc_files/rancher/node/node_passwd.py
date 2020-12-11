import os


def render(service, middleware):
    k8s_config = middleware.call_sync('kubernetes.config')
    if not k8s_config['dataset']:
        return

    k3s_node_passwd_file = os.path.join('/mnt', k8s_config['dataset'], 'k3s/server/cred/node-passwd')
    if not os.path.exists(k3s_node_passwd_file):
        # The only time this will happen is the first time k8s is configured and at that time it's okay
        # as k3s will populate the correct password under /etc but on subsequent upgrades of the system
        # that will be lost
        return

    with open(k3s_node_passwd_file, 'r') as f:
        passwd = f.read().strip().split(',')[0].strip()

    os.makedirs('/etc/rancher/node', exist_ok=True)
    with open('/etc/rancher/node/password', 'w') as f:
        f.write(passwd)
