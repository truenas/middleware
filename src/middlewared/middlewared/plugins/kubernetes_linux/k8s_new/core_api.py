from .client import K8sClientBase
from .exceptions import ApiException
from .utils import NODE_NAME, UPDATE_HEADERS


class CoreAPI(K8sClientBase):

    NAMESPACE = '/api/v1/namespaces'

    @classmethod
    async def query(cls, *args, **kwargs):
        return await cls.call(cls.uri(namespace=kwargs.pop('namespace', None), parameters=kwargs), mode='get')

    @classmethod
    async def create(cls, data: dict, **kwargs):
        return await cls.call(cls.uri(
            namespace=kwargs.pop('namespace', None), parameters=kwargs,
        ), body=data, mode='post')

    @classmethod
    async def update(cls, name: str, data: dict, **kwargs):
        return await cls.call(cls.uri(
            namespace=kwargs.pop('namespace', None), parameters=kwargs, object_name=name,
        ), body=data, mode='patch', headers=UPDATE_HEADERS)

    @classmethod
    async def delete(cls, name: str, **kwargs):
        return await cls.call(cls.uri(
            object_name=name, namespace=kwargs.pop('namespace', None), parameters=kwargs,
        ), mode='delete')


class Namespace(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/namespaces'


class Node(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/nodes'

    @classmethod
    async def get_instance(cls) -> dict:
        node_object = (await cls.query(fieldSelector=f'metadata.name={NODE_NAME}'))
        if not node_object['items']:
            raise ApiException(f'Unable to find "{NODE_NAME}" node.')
        else:
            return node_object['items'][0]

    @classmethod
    async def add_taint(cls, taint_dict: dict) -> None:
        for k in ('key', 'effect'):
            assert k in taint_dict

        node_object = await cls.get_instance()
        existing_taints = []
        for taint in (node_object['spec']['taints'] if node_object['spec'].get('taints') else []):
            if all(taint[k] == taint_dict[k] for k in ('key', 'effect', 'value')):
                return
            existing_taints.append(taint)

        await cls.update(
            node_object['metadata']['name'], {'spec': {'taints': existing_taints + [taint_dict]}}
        )

    @classmethod
    async def remove_taint(cls, taint_key: str) -> None:
        node_object = await cls.get_instance()
        taints = node_object['spec']['taints'] or []

        indexes = []
        for index, taint in enumerate(taints):
            if taint['key'] == taint_key:
                indexes.append(index)

        if not indexes:
            raise ApiException(f'Unable to find taint with "{taint_key}" key')

        for index in sorted(indexes, reverse=True):
            taints.pop(index)

        await cls.update(node_object['metadata']['name'], {'spec': {'taints': taints}})


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
