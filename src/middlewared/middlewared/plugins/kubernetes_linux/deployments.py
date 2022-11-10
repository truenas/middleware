from .k8s_base_resources import KubernetesBaseResource
from .k8s_new import Deployment


class KubernetesDeploymentService(KubernetesBaseResource):

    KUBERNETES_RESOURCE = Deployment

    class Config:
        namespace = 'k8s.deployment'
        private = True
