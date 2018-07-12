from middlewared.client import ejson as json
from middlewared.schema import Any, Str, accepts
from middlewared.service import Service


class KeyValueService(Service):

    class Config:
        private = True

    @accepts(Str('key'))
    async def has_key(self, key):
        try:
            await self.get(key)
            return True
        except KeyError:
            return False

    @accepts(Str('key'))
    async def get(self, key):
        try:
            return json.loads(
                (await self.middleware.call(
                    "datastore.query", "system.keyvalue", [["key", "=", key]], {"get": True}))["value"])
        except IndexError:
            raise KeyError(key)

    @accepts(Str('key'), Any('value'))
    async def set(self, key, value):
        try:
            row = await self.middleware.call("datastore.query", "system.keyvalue", [["key", "=", key]], {"get": True})
        except IndexError:
            await self.middleware.call("datastore.insert", "system.keyvalue", {
                "key": key,
                "value": json.dumps(value)
            })
        else:
            await self.middleware.call("datastore.update", "system.keyvalue", row["id"], {
                "value": json.dumps(value)
            })

        return value
