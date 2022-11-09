from .client import K8sClientBase
from .utils import UPDATE_HEADERS


class CoreAPI(K8sClientBase):

    NAMESPACE = '/api/v1/namespaces'

    @classmethod
    async def query(cls, *args, **kwargs):
        return await cls.call(cls.uri(namespace=kwargs.pop('namespace', None), parameters=kwargs), mode='get')

    @classmethod
    async def create(cls, data, **kwargs):
        return await cls.call(cls.uri(
            namespace=kwargs.pop('namespace', None), parameters=kwargs,
        ), body=data, mode='post')

    @classmethod
    async def update(cls, name, data, **kwargs):
        return await cls.call(cls.uri(
            namespace=kwargs.pop('namespace', None), parameters=kwargs, object_name=name,
        ), body=data, mode='patch', headers=UPDATE_HEADERS)

    @classmethod
    async def delete(cls, name, **kwargs):
        return await cls.call(cls.uri(
            object_name=name, namespace=kwargs.pop('namespace', None), parameters=kwargs,
        ), mode='delete')


class Namespace(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/namespaces'


class Node(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/nodes'


class Service(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/services'
    OBJECT_TYPE = 'services'


class Pod(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/pods'
    OBJECT_TYPE = 'pods'


class Event(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/events'
    OBJECT_TYPE = 'events'


class Secret(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/secrets'
    OBJECT_TYPE = 'secrets'


class PersistentVolume(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/persistentvolumes'
    OBJECT_TYPE = 'persistentvolumes'


class PersistentVolumeClaim(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/persistentvolumeclaims'
    OBJECT_TYPE = 'persistentvolumeclaims'


class Configmap(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/configmaps'
    OBJECT_TYPE = 'configmaps'


class ServicesAccount(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/serviceaccounts'
    OBJECT_TYPE = 'serviceaccounts'
