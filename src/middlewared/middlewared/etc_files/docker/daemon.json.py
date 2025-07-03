import json
import os
import subprocess
from urllib.parse import urlparse

from middlewared.plugins.etc import FileShouldNotExist
from middlewared.plugins.docker.state_utils import IX_APPS_MOUNT_PATH
from middlewared.utils.gpu import get_nvidia_gpus


def render(service, middleware):
    config = middleware.call_sync('docker.config')
    http_proxy = middleware.call_sync('network.configuration.config')['httpproxy']
    if not config['pool']:
        raise FileShouldNotExist()

    # We need to do this so that proxy changes are respected by systemd on docker daemon start
    subprocess.run(['systemctl', 'daemon-reload'], capture_output=True, check=True)

    os.makedirs('/etc/docker', exist_ok=True)
    data_root = os.path.join(IX_APPS_MOUNT_PATH, 'docker')
    base = {
        'data-root': data_root,
        'exec-opts': ['native.cgroupdriver=cgroupfs'],
        'iptables': True,
        'ipv6': True,
        'default-network-opts': {'bridge': {'com.docker.network.enable_ipv6': 'true'}},
        'storage-driver': 'overlay2',
        'fixed-cidr-v6': config['cidr_v6'],
        'default-address-pools': config['address_pools'],
        'registry-mirrors': config['secure_registry_mirrors'],
        'insecure-registries': [urlparse(registry_url).netloc for registry_url in config['insecure_registry_mirrors']]
        **(
            {
                'proxies': {
                    'http-proxy': http_proxy,
                    'https-proxy': http_proxy,
                }
            } if http_proxy else {}
        )
    }

    isolated = middleware.call_sync('system.advanced.config')['isolated_gpu_pci_ids']
    for gpu in filter(lambda x: x not in isolated, get_nvidia_gpus()):
        base.update({
            'runtimes': {
                'nvidia': {
                    'path': '/usr/bin/nvidia-container-runtime',
                    'runtimeArgs': []
                }
            },
            'default-runtime': 'nvidia',
        })
        break

    return json.dumps(base)
