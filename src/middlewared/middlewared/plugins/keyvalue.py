from middlewared.client import ejson as json
from middlewared.schema import Any, Str, accepts
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

    @accepts(Str('key'))
    async def has_key(self, key):
        try:
            await self.get(key)
            return True
        except KeyError:
            return False

    @accepts(Str('key'), Any('default', null=True, default=None))
    async def get(self, key, default):
        try:
            return json.loads(
                (await self.middleware.call(
                    "datastore.query", "system.keyvalue", [["key", "=", key]], {"get": True}))["value"])
        except IndexError:
            if default is not None:
                return default

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

    @accepts(Str('key'))
    async def delete(self, key):
        await self.middleware.call("datastore.delete", "system.keyvalue", [["key", "=", key]])
