from middlewared.service import CRUDService

from .k8s_base_resources import KubernetesBaseResource
from .k8s_new import Deployment


class KubernetesDeploymentService(KubernetesBaseResource, CRUDService):

    KUBERNETES_RESOURCE = Deployment

    class Config:
        namespace = 'k8s.deployment'
        private = True
