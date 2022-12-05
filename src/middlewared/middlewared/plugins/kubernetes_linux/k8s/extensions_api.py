from .client import K8sClientBase


class ApiExtensions(K8sClientBase):

    NAMESPACE = '/apis/apiextensions.k8s.io/v1/customresourcedefinitions'


class CRD(ApiExtensions):

    OBJECT_ENDPOINT = '/apis/apiextensions.k8s.io/v1/customresourcedefinitions'
    OBJECT_HUMAN_NAME = 'Custom Resource Definition'
