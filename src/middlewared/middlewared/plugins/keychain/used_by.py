from __future__ import annotations

import enum
from typing import TYPE_CHECKING, cast

from middlewared.api.current import (
    CredentialsEntry,
    KeychainCredentialDeleteOptions,
    KeychainCredentialEntry,
    ReplicationEntry,
    RsyncTaskEntry,
    SFTPCredentialsModel,
    SSHCredentialsEntry,
    UsedKeychainCredential,
)

if TYPE_CHECKING:
    from middlewared.api.current import RsyncTaskEntry
    from middlewared.main import Middleware

    from . import KeychainCredentialService


class KeychainCredentialUsedByDelegateUnbindMethod(enum.Enum):
    DELETE = "delete"
    DISABLE = "disable"


class KeychainCredentialUsedByDelegate[E]:
    unbind_method: KeychainCredentialUsedByDelegateUnbindMethod

    def __init__(self, middleware: Middleware):
        self.middleware = middleware

    async def query(self, id_: int) -> list[E]:
        raise NotImplementedError

    async def get_title(self, row: E) -> str:
        raise NotImplementedError

    async def unbind(self, row: E) -> None:
        raise NotImplementedError


class OtherKeychainCredentialKeychainCredentialUsedByDelegate[E: KeychainCredentialEntry](
    KeychainCredentialUsedByDelegate[E]
):
    unbind_method = KeychainCredentialUsedByDelegateUnbindMethod.DELETE

    type: str

    async def query(self, id_: int) -> list[E]:
        result: list[E] = []
        for row in await self.middleware.call2(
            self.middleware.services.keychaincredential.query,
            [["type", "=", self.type]],
        ):
            if await self._is_related(row, id_):  # type: ignore[arg-type]
                result.append(row)  # type: ignore[arg-type]

        return result

    async def get_title(self, row: E) -> str:
        from .types import TYPES

        return f"{TYPES[self.type].title} {row.name}"

    async def unbind(self, row: E) -> None:
        await self.middleware.call2(
            self.middleware.services.keychaincredential.delete,
            row.id,
            KeychainCredentialDeleteOptions(cascade=True),
        )

    async def _is_related(self, row: E, id_: int) -> bool:
        raise NotImplementedError


class SSHCredentialsSSHKeyPairUsedByDelegate(
    OtherKeychainCredentialKeychainCredentialUsedByDelegate[SSHCredentialsEntry]
):
    type = "SSH_CREDENTIALS"

    async def _is_related(self, row: SSHCredentialsEntry, id_: int) -> bool:
        return row.attributes.get_secret_value().private_key == id_


class SFTPCloudSyncCredentialsSSHKeyPairUsedByDelegate(KeychainCredentialUsedByDelegate[CredentialsEntry]):
    unbind_method = KeychainCredentialUsedByDelegateUnbindMethod.DISABLE

    async def query(self, id_: int) -> list[CredentialsEntry]:
        result = []
        for cloud_credentials in await self.middleware.call2(
            self.middleware.services.cloudsync.credentials.query, [["provider.type", "=", "SFTP"]]
        ):
            provider = cast(SFTPCredentialsModel, cloud_credentials.provider)
            if provider.private_key.get_secret_value() == id_:
                result.append(cloud_credentials)

        return result

    async def get_title(self, row: CredentialsEntry) -> str:
        return f"Cloud credentials {row.name}"

    async def unbind(self, row: CredentialsEntry) -> None:
        attributes = row.provider.model_dump(expose_secrets=True)
        attributes.pop("type", None)
        attributes.pop("private_key", None)
        await self.middleware.call(
            "datastore.update",
            "system.cloudcredentials",
            row.id,
            {
                "attributes": attributes,
            },
        )


class ReplicationTaskSSHCredentialsUsedByDelegate(KeychainCredentialUsedByDelegate[ReplicationEntry]):
    unbind_method = KeychainCredentialUsedByDelegateUnbindMethod.DISABLE

    async def query(self, id_: int) -> list[ReplicationEntry]:
        return await self.middleware.call2(
            self.middleware.services.replication.query,
            [["ssh_credentials.id", "=", id_]],
        )

    async def get_title(self, row: ReplicationEntry) -> str:
        return f"Replication task {row.name}"

    async def unbind(self, row: ReplicationEntry) -> None:
        await self.middleware.call(
            "datastore.update",
            "storage.replication",
            row.id,
            {
                "repl_enabled": False,
                "repl_ssh_credentials": None,
            },
        )
        await self.middleware.call("zettarepl.update_tasks")


class RsyncTaskSSHCredentialsUsedByDelegate(KeychainCredentialUsedByDelegate[RsyncTaskEntry]):
    unbind_method = KeychainCredentialUsedByDelegateUnbindMethod.DISABLE

    async def query(self, id_: int) -> list[RsyncTaskEntry]:
        return await self.middleware.call2(self.middleware.services.rsynctask.query, [["ssh_credentials.id", "=", id_]])

    async def get_title(self, row: RsyncTaskEntry) -> str:
        return f"Rsync task for {row.path!r}"

    async def unbind(self, row: RsyncTaskEntry) -> None:
        await self.middleware.call2(self.middleware.services.rsynctask.update, row.id, {"enabled": False})
        await self.middleware.call(
            "datastore.update",
            "tasks.rsync",
            row.id,
            {
                "rsync_ssh_credentials": None,
            },
        )


async def get_used_by(service: KeychainCredentialService, id_: int) -> list[UsedKeychainCredential]:
    """Return the list of objects that use the keychain credential with the given ``id``."""
    from .types import TYPES

    instance = await service.get_instance(id_)

    result = []
    for delegate_cls in TYPES[instance.type].used_by_delegates:
        delegate = delegate_cls(service.middleware)
        for row in await delegate.query(instance.id):
            result.append(
                UsedKeychainCredential(
                    title=await delegate.get_title(row),
                    unbind_method=delegate.unbind_method.value,
                )
            )
            if isinstance(delegate, OtherKeychainCredentialKeychainCredentialUsedByDelegate):
                result.extend(await get_used_by(service, row.id))
    return result
