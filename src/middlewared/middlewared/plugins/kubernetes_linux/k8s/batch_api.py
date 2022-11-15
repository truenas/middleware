from .client import K8sClientBase


class BatchApi(K8sClientBase):

    NAMESPACE = '/apis/batch/v1/namespaces'


class Job(BatchApi):

    OBJECT_ENDPOINT = '/apis/batch/v1/jobs'
    OBJECT_HUMAN_NAME = 'Job'
    OBJECT_TYPE = 'jobs'


class CronJob(BatchApi):

    OBJECT_ENDPOINT = '/apis/batch/v1/cronjobs'
    OBJECT_HUMAN_NAME = 'Cron job'
    OBJECT_TYPE = 'cronjobs'
