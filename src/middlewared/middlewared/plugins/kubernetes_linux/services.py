from .k8s_base_resources import KubernetesBaseResource
from .k8s_new import Service


class KubernetesServicesService(KubernetesBaseResource):

    KUBERNETES_RESOURCE = Service

    class Config:
        namespace = 'k8s.service'
        private = True
