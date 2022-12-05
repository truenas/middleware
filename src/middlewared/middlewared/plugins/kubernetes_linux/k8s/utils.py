import enum
import os
import subprocess

from middlewared.plugins.kubernetes_linux.utils import KUBECONFIG_FILE, NODE_NAME  # noqa
from middlewared.utils import run


UPDATE_HEADERS = {
    'Content-Type': 'application/merge-patch+json',
}


class RequestMode(enum.Enum):

    DELETE: str = 'delete'
    GET: str = 'get'
    PATCH: str = 'patch'
    POST: str = 'post'


async def apply_yaml_file(file_path: str) -> subprocess.CompletedProcess:
    return await run(['k3s', 'kubectl', 'apply', '-f', file_path], env=dict(os.environ, KUBECONFIG=KUBECONFIG_FILE))
