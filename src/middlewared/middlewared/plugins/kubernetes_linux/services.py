from middlewared.service import CRUDService

from .k8s_base_resources import KubernetesBaseResource
from .k8s_new import Service


class KubernetesServicesService(KubernetesBaseResource, CRUDService):

    KUBERNETES_RESOURCE = Service

    class Config:
        namespace = 'k8s.service'
        private = True
