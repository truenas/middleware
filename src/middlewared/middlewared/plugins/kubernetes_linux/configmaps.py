from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s_new import Configmap


class KubernetesSecretService(CRUDService):

    class Config:
        namespace = 'k8s.configmap'
        private = True

    @filterable
    async def query(self, filters, options):
        options = options or {}
        label_selector = options.get('extra', {}).get('labelSelector')
        kwargs = {k: v for k, v in [('labelSelector', label_selector)] if v}
        return filter_list((await Configmap.query(**kwargs))['items'], filters, options)
