from typing import Optional

from .client import K8sClientBase


class CustomObject(K8sClientBase):

    @classmethod
    def uri(
        cls, group: str, version: str, plural: Optional[str] = None, name: Optional[str] = None,
        namespace: Optional[str] = None, parameters: Optional[dict] = None
    ) -> str:
        uri = f'/apis/{group}/{version}'
        if namespace:
            uri += f'/namespaces/{namespace}/{plural}'
            return uri + f'/{name}' if name else uri

        return uri + f'/{plural}' + cls.query_selectors(parameters if parameters else {})

    @classmethod
    async def query(cls, group: str, version: str, plural: str, **kwargs):
        return await cls.call(
            cls.uri(group, version, plural, namespace=kwargs.pop('namespace', None), parameters=kwargs), mode='get'
        )

    @classmethod
    async def create(cls, group: str, version: str, plural: str, data: dict, **kwargs):
        return await cls.call(cls.uri(
            group, version, plural, namespace=kwargs.pop('namespace', None), parameters=kwargs), body=data, mode='post'
        )

    @classmethod
    async def delete(cls, group: str, version: str, plural: str, name: str,  **kwargs):
        return await cls.call(
            cls.uri(group, version, plural, name, namespace=kwargs.pop('namespace', None), parameters=kwargs),
            mode='delete',
        )
