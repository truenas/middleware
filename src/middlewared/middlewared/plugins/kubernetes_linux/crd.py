from middlewared.service import CRUDService

from .k8s_base_resources import KubernetesBaseResource
from .k8s_new import CRD


class KubernetesCRDService(KubernetesBaseResource, CRUDService):

    KUBERNETES_RESOURCE = CRD

    class Config:
        namespace = 'k8s.crd'
        private = True
