import aiohttp
import aiohttp.client_exceptions
import asyncio
import async_timeout
import os
import typing
import urllib.parse

from .config import Config, get_config
from .exceptions import ApiException


class ClientMixin:

    @classmethod
    async def api_call(
        cls, endpoint: str, mode: str, body: typing.Any = None, headers: typing.Optional[dict] = None,
        response_type: str = 'json', timeout: int = 50
    ) -> typing.Union[dict, str]:
        try:
            async with async_timeout.timeout(timeout):
                async with aiohttp.ClientSession(
                    connector=aiohttp.TCPConnector(ssl=get_config().ssl_context)
                ) as session:
                    async with await getattr(session, mode)(
                        urllib.parse.urljoin(get_config().server, endpoint), json=body, headers=headers
                    ) as req:
                        if req.status not in (200, 201):
                            raise ApiException(f'Received {req.status!r} response code from {endpoint!r}')

                        return await req.json() if response_type == 'json' else await req.text()
        except (asyncio.TimeoutError, aiohttp.ClientResponseError) as e:
            raise ApiException(f'Failed {endpoint!r} call: {e!r}')
        except aiohttp.client_exceptions.ContentTypeError as e:
            raise ApiException(f'Malformed response received from {endpoint!r} endpoint')


class K8sClientBase(ClientMixin):

    NAMESPACE: str = NotImplementedError
    OBJECT_ENDPOINT: str = NotImplementedError
    OBJECT_TYPE: str = NotImplementedError

    @classmethod
    def query_selectors(cls, parameters: typing.Optional[dict]) -> str:
        return f'?{urllib.parse.urlencode(parameters)}' if parameters else ''

    @classmethod
    def uri(
        cls, namespace: typing.Optional[str] = None, object_name: typing.Optional[str] = None,
        parameters: typing.Optional[dict] = None,
    ) -> str:
        return (os.path.join(
            cls.NAMESPACE, namespace, cls.OBJECT_TYPE, *([object_name] if object_name else [])
        ) if namespace else os.path.join(cls.OBJECT_ENDPOINT, *(
            [object_name] if object_name else []
        ))) + cls.query_selectors(parameters)

    @classmethod
    async def call(
        cls, uri: str, mode: str, body: typing.Any = None, headers: typing.Optional[dict] = None, **kwargs
    ):
        return await cls.api_call(uri, mode, body, headers, **kwargs)
