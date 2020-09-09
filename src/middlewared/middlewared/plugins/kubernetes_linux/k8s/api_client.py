from contextlib import asynccontextmanager
from kubernetes_asyncio import client, config
from kubernetes_asyncio.client.api_client import ApiClient

from .nodes import get_node
from .utils import KUBECONFIG_FILE


@asynccontextmanager
async def api_client(context=None, api_client_kwargs=None):
    await config.load_kube_config(config_file=KUBECONFIG_FILE)
    context = context or {}
    context['core_api'] = True
    api_cl = ApiClient(**(api_client_kwargs or {}))
    user_context = {
        'core_api': client.CoreV1Api(api_cl),
        'apps_api': client.AppsV1Api(api_cl),
        'storage_api': client.StorageV1Api(api_cl),
    }
    for k in filter(lambda k: context[k], context):
        if k == 'node':
            user_context[k] = await get_node(user_context['core_api'])

    try:
        yield api_cl, user_context
    finally:
        await api_cl.close()
