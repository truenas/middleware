from middlewared.service import CRUDService

from .k8s_base_resources import KubernetesBaseResource
from .k8s_new import PersistentVolumeClaim


class KubernetesPersistentVolumeClaimService(KubernetesBaseResource, CRUDService):

    KUBERNETES_RESOURCE = PersistentVolumeClaim

    class Config:
        namespace = 'k8s.pvc'
        namespace_alias = 'k8s.persistent_volume_claim'
        private = True
