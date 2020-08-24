import json
import os


def render(service, middleware):
    config = middleware.call_sync('kubernetes.config')
    if not config['pool']:
        return

    # TODO: Add GPU support
    # TODO: Test proxy support

    os.makedirs('/etc/docker', exist_ok=True)
    with open('/etc/docker/daemon.json', 'w') as f:
        f.write(json.dumps({
            'data-root': os.path.join(config['dataset'], 'docker'),
            'exec-opts': ['native.cgroupdriver=cgroupfs'],
            'iptables': False,
            'bridge': 'none',
        }))
