from .k8s_base_resources import KubernetesBaseResource
from .k8s_new import Job


class KubernetesJobService(KubernetesBaseResource):

    KUBERNETES_RESOURCE = Job

    class Config:
        namespace = 'k8s.job'
        private = True
