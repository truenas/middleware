from __future__ import annotations

from typing import Any, TYPE_CHECKING

import middlewared.sqlalchemy as sa
from middlewared.api.base.jsonschema import get_json_schema
from middlewared.api.current import (
    ACMEDNSAuthenticatorCreate, ACMEDNSAuthenticatorUpdate, DNSAuthenticatorEntry,
)
from middlewared.service import CRUDServicePart, ValidationErrors

from .authenticators.base import Authenticator
from .authenticators.factory import auth_factory

if TYPE_CHECKING:
    from middlewared.api.base import BaseModel


class ACMEDNSAuthenticatorModel(sa.Model):
    __tablename__ = 'system_acmednsauthenticator'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(64), unique=True)
    attributes = sa.Column(sa.JSON(dict, encrypted=True))


class DNSAuthenticatorServicePart(CRUDServicePart[DNSAuthenticatorEntry]):
    _datastore = 'system.acmednsauthenticator'
    _entry = DNSAuthenticatorEntry
    _schemas: dict[str, type[BaseModel]] | None = None

    async def do_create(self, data: ACMEDNSAuthenticatorCreate) -> DNSAuthenticatorEntry:
        data_dict = data.model_dump(context={'expose_secrets': True})
        await self._validate(data_dict, 'dns_authenticator_create')
        return await self._create(data_dict)

    async def do_update(self, id_: int, data: ACMEDNSAuthenticatorUpdate) -> DNSAuthenticatorEntry:
        old = await self.get_instance(id_)
        old_dict = old.model_dump(context={'expose_secrets': True})
        original_name = old_dict['name']
        original_authenticator = old_dict['attributes']['authenticator']

        update_dict = data.model_dump(context={'expose_secrets': True}, exclude_unset=True)
        old_dict.update(update_dict)

        await self._validate(
            old_dict, 'dns_authenticator_update',
            old_name=original_name,
            old_authenticator=original_authenticator,
        )
        return await self._update(id_, old_dict)

    async def do_delete(self, id_: int) -> bool:
        await self.middleware.call('certificate.delete_domains_authenticator', id_)
        await self._delete(id_)
        return True

    async def _validate(
        self,
        data: dict[str, Any],
        schema_name: str,
        *,
        old_name: str | None = None,
        old_authenticator: str | None = None,
    ) -> None:
        verrors = ValidationErrors()
        filters: list[Any] = []
        if old_name is not None:
            filters.append(['name', '!=', old_name])
        filters.append(['name', '=', data['name']])
        if await self.query(filters):
            verrors.add(f'{schema_name}.name', 'Specified name is already in use')

        if old_authenticator is not None and old_authenticator != data['attributes']['authenticator']:
            verrors.add(
                f'{schema_name}.attributes.authenticator',
                'Authenticator cannot be changed',
            )

        authenticator_obj = self.get_authenticator_internal(data['attributes']['authenticator'])
        data['attributes'] = await authenticator_obj.validate_credentials(
            self.middleware, data['attributes']
        )

        verrors.check()

    @staticmethod
    def get_authenticator_internal(authenticator_name: str) -> type[Authenticator]:
        return auth_factory.authenticator(authenticator_name)

    def get_authenticator_schemas(self) -> dict[str, type[BaseModel]]:
        if self._schemas:
            return self._schemas
        authenticators = auth_factory.get_authenticators()
        self._schemas = {k: klass.SCHEMA_MODEL for k, klass in authenticators.items()}
        return self._schemas

    def authenticator_schemas(self) -> list[dict[str, Any]]:
        schemas = self.get_authenticator_schemas()
        return [
            {'schema': get_json_schema(model)[0], 'key': key}
            for key, model in schemas.items()
        ]
