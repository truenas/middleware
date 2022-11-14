import asyncio
import contextlib
import typing

from aiohttp.client_exceptions import ClientConnectionError
from dateutil.parser import parse as datetime_parse

from .client import K8sClientBase
from .exceptions import ApiException
from .utils import NODE_NAME
from .watch import Watch


class CoreAPI(K8sClientBase):

    NAMESPACE = '/api/v1/namespaces'


class Namespace(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/namespaces'


class Node(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/nodes'
    OBJECT_HUMAN_NAME = 'Node'

    @classmethod
    async def get_instance(cls, **kwargs) -> dict:
        return await super().get_instance(NODE_NAME, **kwargs)

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
    OBJECT_HUMAN_NAME = 'Service'
    OBJECT_TYPE = 'services'


class Pod(CoreAPI, Watch):

    OBJECT_ENDPOINT = '/api/v1/pods'
    OBJECT_HUMAN_NAME = 'Pod'
    OBJECT_TYPE = 'pods'

    @classmethod
    async def logs(cls, pod_name: str, namespace: str, **kwargs) -> str:
        return await cls.call(
            cls.uri(namespace, pod_name + '/log', parameters=kwargs), mode='get', response_type='text'
        )

    @classmethod
    async def stream_logs(cls, pod_name: str, namespace: str, **kwargs) -> typing.Generator[str]:
        with contextlib.suppress(ClientConnectionError):
            async with cls.stream(
                cls.uri(namespace, pod_name + '/log', parameters={
                    'follow': True,
                    'timestamp': True,
                    **kwargs,
                }), mode='get', response_type='text',
            ) as stream:
                yield stream


class Event(CoreAPI, Watch):

    OBJECT_ENDPOINT = '/api/v1/events'
    OBJECT_HUMAN_NAME = 'Event'
    OBJECT_TYPE = 'events'

    @classmethod
    def sanitize_data(cls, data: bytes, response_type: str) -> typing.Union[dict, str]:
        sanitized = super().sanitize_data(data, response_type)
        for event in filter(lambda e: e['metadata'].get('creationTimestamp'), sanitized):
            # TODO: Let's remove this in next major release as this is required right now for backwards
            #  compatibility with existing consumers i.e UI
            event['metadata']['creation_timestamp'] = datetime_parse(event['metadata']['creationTimestamp'])

        return sanitized

    @classmethod
    async def stream(cls, **kwargs) -> typing.Generator[dict, str]:
        async with super().stream(
            cls.uri(namespace=kwargs.pop('namespace', None), parameters={**kwargs, 'watch': True, 'timestamp': True}),
            'get', 'json',
        ) as stream:
            yield stream


class Secret(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/secrets'
    OBJECT_HUMAN_NAME = 'Secret'
    OBJECT_TYPE = 'secrets'


class PersistentVolume(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/persistentvolumes'
    OBJECT_HUMAN_NAME = 'Persistent Volume'
    OBJECT_TYPE = 'persistentvolumes'


class PersistentVolumeClaim(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/persistentvolumeclaims'
    OBJECT_HUMAN_NAME = 'Persistent Volume Claim'
    OBJECT_TYPE = 'persistentvolumeclaims'


class Configmap(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/configmaps'
    OBJECT_HUMAN_NAME = 'Configmap'
    OBJECT_TYPE = 'configmaps'


class ServiceAccount(CoreAPI):

    OBJECT_ENDPOINT = '/api/v1/serviceaccounts'
    OBJECT_HUMAN_NAME = 'Service Account'
    OBJECT_TYPE = 'serviceaccounts'

    @classmethod
    async def create_token(cls, name: str, data: dict, **kwargs) -> str:
        return (await cls.call(cls.uri(
            object_name=name + '/token', namespace=kwargs.pop('namespace', None), parameters=kwargs,
        ), body=data, mode='post'))['status']['token']

    @classmethod
    async def safely_create_token(cls, service_account_name: str) -> str:
        while True:
            try:
                service_account_details = await cls.get_instance(service_account_name)
            except Exception:
                await asyncio.sleep(5)
            else:
                break

        return await cls.create_token(
            service_account_name, {'spec': {'expirationSeconds': 500000000}},
            namespace=service_account_details['metadata']['namespace'],
        )
