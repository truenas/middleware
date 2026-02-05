from typing import Any

from truenas_api_client import json

from middlewared.service import Service
import middlewared.sqlalchemy as sa


class KeyValueModel(sa.Model):
    __tablename__ = 'system_keyvalue'

    id = sa.Column(sa.Integer(), primary_key=True)
    key = sa.Column(sa.String(255), unique=True)
    value = sa.Column(sa.Text())


class KeyValueService(Service):

    class Config:
        private = True

    async def has_key(self, key: str) -> bool:
        try:
            await self.get(key)
            return True
        except KeyError:
            return False

    async def get(self, key: str, default: Any | None = None) -> Any:
        try:
            return json.loads(
                (await self.middleware.call(
                    "datastore.query", "system.keyvalue", [["key", "=", key]], {"get": True}))["value"])
        except IndexError:
            if default is not None:
                return default

            raise KeyError(key)

    async def set(self, key: str, value: Any, options: dict[str, Any] | None = None) -> None:
        opts = options if options is not None else dict()
        try:
            row = await self.middleware.call("datastore.query", "system.keyvalue", [["key", "=", key]], {"get": True})
        except IndexError:
            await self.middleware.call(
                "datastore.insert", "system.keyvalue", {"key": key, "value": json.dumps(value)}, opts
            )
        else:
            await self.middleware.call(
                "datastore.update", "system.keyvalue", row["id"], {"value": json.dumps(value)}, opts
            )

    async def delete(self, key: str, options: dict[str, Any] | None = None) -> None:
        opts = options if options is not None else dict()
        await self.middleware.call("datastore.delete", "system.keyvalue", [["key", "=", key]], opts)
