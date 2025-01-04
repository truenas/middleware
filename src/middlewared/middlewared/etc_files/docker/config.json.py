import json
import os

from middlewared.plugins.app_registry.utils import generate_docker_auth_config
from middlewared.plugins.etc import FileShouldNotExist


def render(service, middleware):
    config = middleware.call_sync('docker.config')
    if not config['pool']:
        raise FileShouldNotExist()

    os.makedirs('/etc/docker', exist_ok=True)

    return json.dumps(generate_docker_auth_config(middleware.call_sync('app.registry.query')))
