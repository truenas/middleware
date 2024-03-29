from middlewared.service import CRUDService

from .k8s_base_resources import KubernetesBaseResource
from .k8s import StatefulSet


class KubernetesStatefulsetService(KubernetesBaseResource, CRUDService):

    KUBERNETES_RESOURCE = StatefulSet

    class Config:
        namespace = 'k8s.statefulset'
        private = True
