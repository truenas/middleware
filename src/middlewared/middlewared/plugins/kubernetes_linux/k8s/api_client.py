from kubernetes_asyncio import client, config
from kubernetes_asyncio.client.api_client import ApiClient

from .utils import KUBECONFIG_FILE


async def api_client(api_client_kwargs=None):
    await config.load_kube_config(config_file=KUBECONFIG_FILE)
    return ApiClient(**(api_client_kwargs or {}))
