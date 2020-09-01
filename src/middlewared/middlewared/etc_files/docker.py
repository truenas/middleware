import json
import os
import subprocess


def render(service, middleware):
    config = middleware.call_sync('kubernetes.config')
    if not config['pool']:
        return

    # TODO: Add GPU support

    # We need to do this so that proxy changes are respected by systemd on docker daemon start
    subprocess.run(['systemctl', 'daemon-reload'], capture_output=True, check=True)

    os.makedirs('/etc/docker', exist_ok=True)
    with open('/etc/docker/daemon.json', 'w') as f:
        f.write(json.dumps({
            'data-root': os.path.join('/mnt', config['dataset'], 'docker'),
            'exec-opts': ['native.cgroupdriver=cgroupfs'],
            'iptables': False,
            'bridge': 'none',
        }))
