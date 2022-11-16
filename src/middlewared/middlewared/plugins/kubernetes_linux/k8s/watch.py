import aiohttp
import asyncio
import json
import typing


from .client import ClientMixin
from .core_api import Event, Pod


class Watch(ClientMixin):

    def __init__(self, resource: typing.Union[Event, Pod], resource_uri_args: typing.Optional[dict] = None):
        self.resource: typing.Union[Event, Pod] = resource
        self.resource_ui_args: typing.Optional[dict] = resource_uri_args or {}
        self.response: typing.Optional[aiohttp.ClientResponse] = None
        self._stop: bool = False

    def stop(self) -> None:
        self._stop = True

    @classmethod
    def sanitize_data(cls, data: bytes, response_type: str) -> typing.Union[dict, str]:
        try:
            data = data.decode()
            return json.loads(data) if response_type == 'json' else data
        except (json.JSONDecodeError, UnicodeDecodeError):
            return data

    @classmethod
    async def stream(cls, endpoint: str, mode: str, response_type: str) -> typing.Union[
        typing.AsyncIterable[dict], typing.AsyncIterable[str]
    ]:
        async with cls.request(endpoint, mode, timeout=1800) as req:
            async for line in req.content:
                yield cls.sanitize_data(line, response_type)

    async def request_args(self, *args, **kwargs):
        raise NotImplementedError

    async def __aenter__(self):
        return self

    async def __anext__(self):
        try:
            return await self.next()
        except Exception:
            await self.close()
            raise

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()

    async def close(self):
        if self.response is not None:
            self.response.release()

    async def next(self):
        while True:
            if self.response is None:
                self.response = None

            # Abort at the current iteration if the user has called `stop` on this
            # stream instance.
            if self._stop:
                raise StopAsyncIteration

            # Fetch the next K8s response.
            try:
                line = await self.resp.content.readline()
            except asyncio.TimeoutError:
                if 'timeout_seconds' not in self.func.keywords:
                    self.resp.close()
                    self.resp = None
                    if self.resource_version:
                        self.func.keywords['resource_version'] = self.resource_version
                    continue
                else:
                    raise

            line = line.decode('utf8')

            # Stop the iterator if K8s sends an empty response. This happens when
            # eg the supplied timeout has expired.
            if line == '':
                raise StopAsyncIteration

            # Special case for faster log streaming
            if self.return_type == 'str':
                return line

            return self.unmarshal_event(line, self.return_type)
