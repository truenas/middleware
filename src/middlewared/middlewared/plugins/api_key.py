from datetime import datetime
import random
import string

from passlib.hash import pbkdf2_sha256

from middlewared.schema import accepts, Bool, Dict, Int, Str, Patch
from middlewared.service import CRUDService, private, ValidationErrors
from middlewared.service_exception import MatchNotFound
import middlewared.sqlalchemy as sa


class APIKeyModel(sa.Model):
    __tablename__ = "account_api_key"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(200))
    key = sa.Column(sa.Text())
    created_at = sa.Column(sa.DateTime())


class ApiKeyService(CRUDService):

    class Config:
        namespace = "api_key"
        datastore = "account.api_key"
        datastore_extend = "api_key.item_extend"
        cli_namespace = "auth.api_key"

    @private
    async def item_extend(self, item):
        item.pop("key")
        return item

    @accepts(
        Dict(
            "api_key_create",
            Str("name", required=True, empty=False),
            register=True
        )
    )
    async def do_create(self, data):
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

        return self._serve(data, key)

    @accepts(
        Int("id", required=True),
        Patch(
            "api_key_create",
            "api_key_update",
            ("add", Bool("reset")),
            ("attr", {"update": True}),
        )
    )
    async def do_update(self, id, data):
        """
        Update API Key `id`.

        Specify `reset: true` to reset this API Key.
        """
        reset = data.pop("reset", False)

        old = await self._get_instance(id)
        new = old.copy()

        new.update(data)

        await self._validate("api_key_update", new, id)

        key = None
        if reset:
            key = self._generate()
            new["key"] = pbkdf2_sha256.encrypt(key)

        await self.middleware.call(
            "datastore.update",
            self._config.datastore,
            id,
            new,
        )

        return self._serve(await self._get_instance(id), key)

    @accepts(
        Int("id")
    )
    async def do_delete(self, id):
        """
        Delete API Key `id`.
        """
        response = await self.middleware.call(
            "datastore.delete",
            self._config.datastore,
            id
        )

        return response

    @private
    async def authenticate(self, key):
        try:
            key_id, key = key.split("-", 1)
            key_id = int(key_id)
        except ValueError:
            return None

        try:
            db_key = await self.middleware.call("datastore.query", "account.api_key", [("id", "=", key_id)],
                                                {"get": True})
        except MatchNotFound:
            return None

        if not pbkdf2_sha256.verify(key, db_key["key"]):
            return None

        return db_key

    async def _validate(self, schema_name, data, id=None):
        verrors = ValidationErrors()

        await self._ensure_unique(verrors, schema_name, "name", data["name"], id)

        if verrors:
            raise verrors

    def _generate(self):
        return "".join([random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(64)])

    def _serve(self, data, key):
        if key is None:
            return data

        return dict(data, key=f"{data['id']}-{key}")
