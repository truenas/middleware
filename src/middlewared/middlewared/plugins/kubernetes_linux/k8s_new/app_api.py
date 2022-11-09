from .client import K8sClientBase


class AppApi(K8sClientBase):

    NAMESPACE = '/apis/apps/v1/namespaces'


class DaemonSet(AppApi):

    OBJECT_ENDPOINT = '/apis/apps/v1/daemonsets'
    OBJECT_HUMAN_NAME = 'Daemonset'
    OBJECT_TYPE = 'daemonsets'


class Deployment(AppApi):

    OBJECT_ENDPOINT = '/apis/apps/v1/deployments'
    OBJECT_HUMAN_NAME = 'Deployment'
    OBJECT_TYPE = 'deployments'


class ReplicaSet(AppApi):

    OBJECT_ENDPOINT = '/apis/apps/v1/replicasets'
    OBJECT_HUMAN_NAME = 'Replicaset'
    OBJECT_TYPE = 'replicasets'


class StatefulSet(AppApi):
    OBJECT_ENDPOINT = '/apis/apps/v1/statefulsets'
    OBJECT_HUMAN_NAME = 'StatefulSet'
    OBJECT_TYPE = 'statefulsets'
