from .k8s_base_resources import KubernetesBaseResource
from .k8s_new import CronJob, Job


class KubernetesJobService(KubernetesBaseResource):

    KUBERNETES_RESOURCE = Job

    class Config:
        namespace = 'k8s.job'
        private = True


class KubernetesCronjobService(KubernetesBaseResource):

    KUBERNETES_RESOURCE = CronJob

    class Config:
        namespace = 'k8s.cronjob'
        private = True
