import json
import os


def render(service, middleware):
    sys_config = middleware.call_sync('systemdataset.config')
    if not sys_config['path']:
        return

    os.makedirs('/etc/docker', exist_ok=True)
    with open('/etc/docker/daemon.json', 'w') as f:
        f.write(json.dumps({
            'data-root': os.path.join(sys_config['path'], 'services/docker'),
            'exec-opts': ['native.cgroupdriver=systemd'],
        }))
