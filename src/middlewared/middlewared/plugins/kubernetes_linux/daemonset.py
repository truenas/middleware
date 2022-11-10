from .k8s_base_resources import KubernetesBaseResource
from .k8s_new import DaemonSet


class KubernetesDaemonsetService(KubernetesBaseResource):

    KUBERNETES_RESOURCE = DaemonSet

    class Config:
        namespace = 'k8s.daemonset'
        private = True
