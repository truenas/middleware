from middlewared.service import CRUDService

from .k8s_base_resources import KubernetesBaseResource
from .k8s import ReplicaSet


class KubernetesReplicaSetService(KubernetesBaseResource, CRUDService):

    KUBERNETES_RESOURCE = ReplicaSet

    class Config:
        namespace = 'k8s.replicaset'
        private = True
