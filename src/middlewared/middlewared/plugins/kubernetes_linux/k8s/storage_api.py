from .client import K8sClientBase


class StorageApi(K8sClientBase):
    pass


class StorageClass(StorageApi):

    OBJECT_ENDPOINT = '/apis/storage.k8s.io/v1/storageclasses'
    OBJECT_HUMAN_NAME = 'Storage Class'
    OBJECT_TYPE = 'storageclasses'
