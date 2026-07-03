from __future__ import annotations

from middlewared.api.current import (
    KeychainCredentialCreate,
    KeychainCredentialDeleteOptions,
    KeychainCredentialEntry,
    KeychainCredentialUpdate,
)
from middlewared.service import CRUDServicePart, ValidationErrors
from middlewared.service_exception import ValidationError
import middlewared.sqlalchemy as sa
from middlewared.utils.types import AuditCallback

from .types import TYPES


class KeychainCredentialModel(sa.Model):
    __tablename__ = "system_keychaincredential"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(255))
    type = sa.Column(sa.String(255))
    attributes = sa.Column(sa.JSON(dict, encrypted=True))


class KeychainCredentialServicePart(CRUDServicePart[KeychainCredentialEntry]):
    _datastore = "system.keychaincredential"
    _entry = KeychainCredentialEntry

    async def do_create(self, data: KeychainCredentialCreate) -> KeychainCredentialEntry:
        await self.validate("keychain_credential_create", data)
        return await self._create(
            {
                "name": data.name,
                "type": data.type,
                "attributes": data.attributes.get_secret_value().model_dump(),
            }
        )

    async def do_update(
        self,
        audit_callback: AuditCallback,
        id_: int,
        data: KeychainCredentialUpdate,
    ) -> KeychainCredentialEntry:
        old = await self.get_instance(id_)
        audit_callback(old.name)

        new = old.updated(data)

        await self.validate("keychain_credentials_update", new, id_)

        entry = await self._update(
            id_,
            {
                "name": new.name,
                "type": new.type,
                "attributes": new.attributes.get_secret_value().model_dump(),
            },
        )

        await self.middleware.call("zettarepl.update_tasks")

        return entry

    async def do_delete(
        self,
        audit_callback: AuditCallback,
        id_: int,
        options: KeychainCredentialDeleteOptions,
    ) -> None:
        instance = await self.get_instance(id_)
        audit_callback(instance.name)

        for delegate_cls in TYPES[instance.type].used_by_delegates:
            delegate = delegate_cls(self.middleware)
            for row in await delegate.query(instance.id):
                if not options.cascade:
                    raise ValidationError(
                        "options.cascade", "This credential is used and no cascade option is specified"
                    )
                await delegate.unbind(row)

        await self._delete(id_)

    async def validate(
        self,
        schema_name: str,
        credential: KeychainCredentialEntry,
        id_: int | None = None,
    ) -> None:
        verrors = ValidationErrors()

        await self._ensure_unique(verrors, schema_name, "name", credential.name, id_)
        verrors.check()

        type_ = TYPES[credential.type]
        attributes = credential.attributes.get_secret_value()
        await type_.validate_and_pre_save(self.middleware, verrors, f"{schema_name}.attributes", attributes)
        verrors.check()
