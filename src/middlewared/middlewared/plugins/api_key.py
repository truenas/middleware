from datetime import datetime
import random
import string
from typing import Any, TYPE_CHECKING

from passlib.hash import pbkdf2_sha256

from middlewared.api import api_method
from middlewared.api.current import (
    ApiKeyCreateArgs, ApiKeyCreateResult, ApiKeyUpdateArgs,
    ApiKeyUpdateResult, ApiKeyDeleteArgs, ApiKeyDeleteResult
)
from middlewared.service import CRUDService, private, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.allowlist import Allowlist
if TYPE_CHECKING:
    from middlewared.main import Middleware


class APIKeyModel(sa.Model):
    __tablename__ = "account_api_key"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(200))
    key = sa.Column(sa.Text())
    created_at = sa.Column(sa.DateTime())
    allowlist = sa.Column(sa.JSON(list))


class ApiKey:
    def __init__(self, api_key: dict[str, list[dict[str, str]]]):
        self.api_key = api_key
        self.allowlist = Allowlist(self.api_key["allowlist"])

    def authorize(self, method: str, resource: str):
        return self.allowlist.authorize(method, resource)


class ApiKeyService(CRUDService):

    keys: dict[int, dict[str, list[dict[str, str]]]] = {}

    class Config:
        namespace = "api_key"
        datastore = "account.api_key"
        datastore_extend = "api_key.item_extend"
        cli_namespace = "auth.api_key"

    @private
    async def item_extend(self, item: dict):
        item.pop("key")
        return item

    @api_method(ApiKeyCreateArgs, ApiKeyCreateResult)
    async def do_create(self, data: dict):
        """
        Creates API Key.

        `name` is a user-readable name for key.
        """
        await self._validate("api_key_create", data)

        key = self._generate()
        data["key"] = pbkdf2_sha256.encrypt(key)

        data["created_at"] = datetime.utcnow()

        data["id"] = await self.middleware.call(
            "datastore.insert",
            self._config.datastore,
            data
        )

        await self.load_key(data["id"])

        return self._serve(data, key)

    @api_method(ApiKeyUpdateArgs, ApiKeyUpdateResult)
    async def do_update(self, id_, data: dict):
        """
        Update API Key `id`.

        Specify `reset: true` to reset this API Key.
        """
        reset = data.pop("reset", False)

        old = await self.get_instance(id_)
        new = old.copy()

        new.update(data)

        await self._validate("api_key_update", new, id_)

        key = None
        if reset:
            key = self._generate()
            new["key"] = pbkdf2_sha256.encrypt(key)

        await self.middleware.call(
            "datastore.update",
            self._config.datastore,
            id_,
            new,
        )

        await self.load_key(id_)

        return self._serve(await self.get_instance(id_), key)

    @api_method(ApiKeyDeleteArgs, ApiKeyDeleteResult)
    async def do_delete(self, id_: int):
        """
        Delete API Key `id`.
        """
        response = await self.middleware.call(
            "datastore.delete",
            self._config.datastore,
            id_
        )

        self.keys.pop(id_)

        return response

    @private
    async def load_keys(self):
        self.keys = {
            key["id"]: key
            for key in await self.middleware.call("datastore.query", "account.api_key")
        }

    @private
    async def load_key(self, id_: int):
        self.keys[id_] = await self.middleware.call(
            "datastore.query",
            "account.api_key",
            [["id", "=", id_]],
            {"get": True},
        )

    @private
    async def authenticate(self, key: str):
        try:
            key_id, key = key.split("-", 1)
            key_id = int(key_id)
        except ValueError:
            return None

        try:
            db_key = self.keys[key_id]
        except KeyError:
            return None

        if not pbkdf2_sha256.verify(key, db_key["key"]):
            return None

        return ApiKey(db_key)

    async def _validate(self, schema_name: str, data: dict, id_=None):
        verrors = ValidationErrors()

        await self._ensure_unique(verrors, schema_name, "name", data["name"], id_)

        verrors.check()

    def _generate(self):
        return "".join([random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(64)])

    def _serve(self, data: dict, key: Any | None):
        if key is None:
            return data

        return dict(data, key=f"{data['id']}-{key}")


async def setup(middleware: 'Middleware'):
    await middleware.call("api_key.load_keys")
