import os
import subprocess

from middlewared.plugins.kubernetes_linux.utils import KUBECONFIG_FILE, NODE_NAME  # noqa
from middlewared.utils import run


UPDATE_HEADERS = {
    'Content-Type': 'application/merge-patch+json',
}


async def apply_yaml_file(file_path: str) -> subprocess.CompletedProcess:
    return await run(['k3s', 'kubectl', 'apply', '-f', file_path], env=dict(os.environ, KUBECONFIG=KUBECONFIG_FILE))
