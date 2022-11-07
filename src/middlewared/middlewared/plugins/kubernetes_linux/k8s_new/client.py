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

    def __init__(self):
        self.config: Config = get_config()

    async def api_call(
        self, endpoint: str, mode: str, body: typing.Any = None, headers: typing.Optional[dict] = None,
        response_type: str = 'json', timeout: int = 50
    ) -> typing.Union[dict, str]:
        try:
            async with async_timeout.timeout(timeout):
                async with aiohttp.ClientSession(
                    connector=aiohttp.TCPConnector(ssl=self.config.ssl_context)
                ) as session:
                    req = await getattr(session, mode)(
                        urllib.parse.urljoin(self.config.server, endpoint), json=body, headers=headers
                    )
        except (asyncio.TimeoutError, aiohttp.ClientResponseError) as e:
            raise ApiException(f'Failed {endpoint!r} call: {e!r}')
        else:
            if req.status != 200:
                raise ApiException(f'Received {req.status!r} response code from {endpoint!r}')

            try:
                return await req.json() if response_type == 'json' else await req.text()
            except aiohttp.client_exceptions.ContentTypeError as e:
                raise ApiException(f'Malformed response received from {endpoint!r} endpoint')
            except asyncio.TimeoutError:
                raise ApiException(f'Timed out waiting for response from {endpoint!r}')


class K8sClientBase(ClientMixin):

    NAMESPACE: str = NotImplementedError
    OBJECT_ENDPOINT: str = NotImplementedError
    OBJECT_TYPE: str = NotImplementedError

    def query_selectors(self, parameters: typing.Optional[dict]) -> str:
        return f'?{urllib.parse.urlencode(parameters)}' if parameters else ''

    def uri(
        self, namespace: typing.Optional[str] = None, object_name: typing.Optional[str] = None,
        parameters: typing.Optional[dict] = None,
    ) -> str:
        return (os.path.join(
            self.NAMESPACE, namespace, self.OBJECT_TYPE, *([object_name] if object_name else [])
        ) if namespace else self.OBJECT_ENDPOINT) + self.query_selectors(parameters)

    def call(
        self, uri: str, mode: str, body: typing.Any = None, headers: typing.Optional[dict] = None, **kwargs
    ):
        return self.api_call(uri, mode, body, headers, **kwargs)
