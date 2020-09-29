import os

from middlewared.utils import run as _run

CHART_NAMESPACE = 'default'


async def run(*args, **kwargs):
    kwargs['env'] = dict(os.environ, KUBECONFIG='/etc/rancher/k3s/k3s.yaml')
    return await _run(*args, **kwargs)
