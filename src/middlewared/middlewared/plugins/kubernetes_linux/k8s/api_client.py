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
    user_context = {}
    for k in filter(lambda k: context[k], context):
        if k == 'core_api':
            user_context[k] = client.CoreV1Api(api_cl)
        elif k == 'node':
            user_context[k] = get_node(api_cl)

    try:
        yield api_cl, user_context
    finally:
        await api_cl.close()
