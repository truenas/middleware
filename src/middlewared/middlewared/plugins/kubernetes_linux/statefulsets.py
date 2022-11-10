from .k8s_base_resources import KubernetesBaseResource
from .k8s_new import StatefulSet


class KubernetesStatefulsetService(KubernetesBaseResource):

    KUBERNETES_RESOURCE = StatefulSet

    class Config:
        namespace = 'k8s.statefulset'
        private = True
