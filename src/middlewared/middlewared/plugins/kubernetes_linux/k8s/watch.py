import json
import typing


from .client import ClientMixin


class Watch(ClientMixin):

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
