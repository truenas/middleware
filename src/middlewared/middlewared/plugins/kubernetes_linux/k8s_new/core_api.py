from .client import K8sClientBase
from .utils import UPDATE_HEADERS


class CoreAPI(K8sClientBase):

    NAMESPACE = '/api/v1/namespaces'

    @classmethod
    async def query(cls, *args, **kwargs):
        return await cls.call(cls.uri(parameters=kwargs), mode='get')

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
