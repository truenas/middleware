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
        **(
            {
                'proxies': {
                    'http-proxy': http_proxy,
                    'https-proxy': http_proxy,
                }
            } if http_proxy else {}
        )
    }

    # Process registry mirrors
    if config.get('registry_mirrors'):
        registry_mirrors = []
        insecure_registries = []

        for registry_url in config['registry_mirrors']:
            parsed = urlparse(registry_url)
            if parsed.scheme == 'http':
                # For HTTP, add to insecure-registries
                insecure_registries.append(parsed.netloc)
            else:
                # For HTTPS, add to registry-mirrors
                registry_mirrors.append(registry_url)

        if registry_mirrors:
            base['registry-mirrors'] = registry_mirrors
        if insecure_registries:
            base['insecure-registries'] = insecure_registries

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
