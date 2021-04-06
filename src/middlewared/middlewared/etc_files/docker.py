import json
import os
import subprocess


def nvidia_configuration(middleware):
    # this needs to happen for nvidia gpu to work properly for docker containers
    # https://github.com/NVIDIA/nvidia-docker/issues/854#issuecomment-572175484
    nvidia_config_path = '/etc/nvidia-container-runtime/config.toml'
    if not os.path.exists(nvidia_config_path):
        return {}

    with open(nvidia_config_path, 'r') as f:
        data = f.read()

    with open(nvidia_config_path, 'w') as f:
        f.write(data.replace('@/sbin/ldconfig', '/sbin/ldconfig'))

    return {
        'runtimes': {'nvidia': {'path': '/usr/bin/nvidia-container-runtime', 'runtimeArgs': []}},
        'default-runtime': 'nvidia',
    }


def gpu_configuration(middleware):
    available_gpus = middleware.call_sync('device.get_info', 'GPU')
    if any(gpu['vendor'] == 'NVIDIA' and gpu['available_to_host'] for gpu in available_gpus):
        return nvidia_configuration(middleware)

    return {}


def render(service, middleware):
    config = middleware.call_sync('kubernetes.config')
    if not config['pool']:
        return

    # We need to do this so that proxy changes are respected by systemd on docker daemon start
    subprocess.run(['systemctl', 'daemon-reload'], capture_output=True, check=True)

    os.makedirs('/etc/docker', exist_ok=True)
    data_root = os.path.join('/mnt', config['dataset'], 'docker')
    with open('/etc/docker/daemon.json', 'w') as f:
        f.write(json.dumps({
            'data-root': data_root.replace(' ', r'\ '),
            'exec-opts': ['native.cgroupdriver=cgroupfs'],
            'iptables': False,
            'bridge': 'none',
            **gpu_configuration(middleware),
        }))
