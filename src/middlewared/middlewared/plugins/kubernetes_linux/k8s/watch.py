import contextlib

import asyncio
import json
import typing


from .client import ClientMixin
from .core_api import Event, Pod
from .exceptions import ApiException


class Watch(ClientMixin):

    def __init__(
        self, resource: typing.Union[typing.Type[Event], typing.Type[Pod]],
        resource_uri_args: typing.Optional[dict] = None,
    ):
        self.resource: typing.Union[typing.Type[Event], typing.Type[Pod]] = resource
        self.resource_ui_args: typing.Optional[dict] = resource_uri_args or {}
        self._stop: bool = False

    async def stop(self) -> None:
        self._stop = True

    @classmethod
    def sanitize_data(cls, data: bytes, response_type: str) -> typing.Union[dict, str]:
        try:
            data = data.decode(errors='ignore')
            return json.loads(data) if response_type == 'json' else data
        except json.JSONDecodeError:
            raise ApiException(f'Failed to parse watch response: {data!r}')

    async def watch(self) -> typing.Union[typing.AsyncIterable[dict], typing.AsyncIterable[str]]:
        while not self._stop:
            with contextlib.suppress(asyncio.TimeoutError):
                async with self.request(
                    await self.resource.stream_uri(**self.resource_ui_args), 'get',
                    timeout=self.resource.STREAM_RESPONSE_TIMEOUT * 60, handle_timeout=False,
                ) as response:
                    async for line in response.content:
                        if self._stop:
                            return

                        yield self.resource.normalize_data(self.sanitize_data(line, self.resource.STREAM_RESPONSE_TYPE))
