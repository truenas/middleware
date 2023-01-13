from middlewared.service import CRUDService

from .k8s_base_resources import KubernetesBaseResource
from .k8s import Configmap


class KubernetesSecretService(KubernetesBaseResource, CRUDService):

    KUBERNETES_RESOURCE = Configmap

    class Config:
        namespace = 'k8s.configmap'
        private = True
