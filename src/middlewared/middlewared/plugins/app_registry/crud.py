from __future__ import annotations

from typing import Any

from middlewared.api.current import AppRegistryCreate, AppRegistryEntry, AppRegistryUpdate
from middlewared.service import CRUDServicePart, ValidationErrors
import middlewared.sqlalchemy as sa

from .validate_registry import validate_registry_credentials


class AppRegistryModel(sa.Model):
    __tablename__ = "app_registry"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(255), nullable=False)
    description = sa.Column(sa.String(512), nullable=True, default=None)
    username = sa.Column(sa.EncryptedText(), nullable=False)
    password = sa.Column(sa.EncryptedText(), nullable=False)
    uri = sa.Column(sa.String(512), nullable=False, unique=True)


class AppRegistryServicePart(CRUDServicePart[AppRegistryEntry]):
    _datastore = "app.registry"
    _entry = AppRegistryEntry

    async def do_create(self, data: AppRegistryCreate) -> AppRegistryEntry:
        await self.middleware.call("docker.validate_state")
        data = await self.validate(data, "app_registry_create")
        entry = await self._create(data.model_dump(context={"expose_secrets": True}))
        await self.middleware.call("etc.generate", "app_registry")
        return entry

    async def do_update(self, id_: int, data: AppRegistryUpdate) -> AppRegistryEntry:
        await self.middleware.call("docker.validate_state")
        old = await self.get_instance(id_)
        new = old.updated(data)
        new = await self.validate(new, "app_registry_update", old=old)
        entry = await self._update(id_, new.model_dump(context={"expose_secrets": True}))
        await self.middleware.call("etc.generate", "app_registry")
        return entry

    async def do_delete(self, id_: int) -> None:
        await self.middleware.call("docker.validate_state")
        await self.get_instance(id_)
        await self._delete(id_)
        await self.middleware.call("etc.generate", "app_registry")

    async def validate[T: AppRegistryEntry](
        self,
        data: T,
        schema: str,
        old: AppRegistryEntry | None = None,
    ) -> T:
        verrors = ValidationErrors()
        filters: list[list[Any]] = [["id", "!=", old.id]] if old else []

        if await self.query([["name", "=", data.name]] + filters):
            verrors.add(f"{schema}.name", "Name must be unique")

        # We can have 2 formats basically
        # https://index.docker.io/v1/
        # registry-1.docker.io
        # We would like to have a trailing slash here because we are not able to pull images without it
        # if http based url is provided
        uri = data.uri
        if uri.startswith("http") and not uri.endswith("/"):
            uri = uri + "/"
            data = data.model_copy(update={"uri": uri})

        if await self.query([["uri", "=", uri]] + filters):
            verrors.add(f"{schema}.uri", "URI must be unique")

        if not verrors and not await self.to_thread(
            validate_registry_credentials,
            uri,
            data.username.get_secret_value(),
            data.password.get_secret_value(),
        ):
            verrors.add(f"{schema}.uri", "Invalid credentials for registry")

        verrors.check()
        return data
