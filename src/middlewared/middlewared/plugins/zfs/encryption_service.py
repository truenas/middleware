from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import Secret

from middlewared.api import api_method
from middlewared.api.current import (
    ZFSResourceEncryptionChangeKeyArgs,
    ZFSResourceEncryptionChangeKeyArgsData,
    ZFSResourceEncryptionChangeKeyResult,
    ZFSResourceEncryptionExportKeyArgs,
    ZFSResourceEncryptionExportKeyArgsData,
    ZFSResourceEncryptionExportKeyResult,
    ZFSResourceEncryptionExportKeysArgs,
    ZFSResourceEncryptionExportKeysArgsData,
    ZFSResourceEncryptionExportKeysResult,
    ZFSResourceEncryptionExportReplicationKeysArgs,
    ZFSResourceEncryptionExportReplicationKeysArgsData,
    ZFSResourceEncryptionExportReplicationKeysResult,
    ZFSResourceEncryptionInheritArgs,
    ZFSResourceEncryptionInheritArgsData,
    ZFSResourceEncryptionInheritResult,
    ZFSResourceEncryptionLockArgs,
    ZFSResourceEncryptionLockArgsData,
    ZFSResourceEncryptionLockResult,
    ZFSResourceEncryptionUnlockArgs,
    ZFSResourceEncryptionUnlockArgsData,
    ZFSResourceEncryptionUnlockEntry,
    ZFSResourceEncryptionUnlockResult,
    ZFSResourceEncryptionUnlockSummaryArgs,
    ZFSResourceEncryptionUnlockSummaryArgsData,
    ZFSResourceEncryptionUnlockSummaryEntry,
    ZFSResourceEncryptionUnlockSummaryResult,
)
from middlewared.service import Service, job, periodic, private
from middlewared.service.decorators import pass_thread_local_storage

from . import encryption_info as _info
from . import encryption_keys as _keys
from . import encryption_lock as _lock
from . import encryption_ops as _ops
from .encryption_job_locks import (
    DATASET_ENCRYPTION_EXPORT_KEYS_LOCK,
    DATASET_ENCRYPTION_LOCK,
    dataset_encryption_change_key_lock,
    dataset_encryption_sync_keys_lock,
    dataset_encryption_unlock_lock,
    dataset_encryption_unlock_summary_lock,
    job_args_path,
)

if TYPE_CHECKING:
    from middlewared.api.current import ReplicationEntry
    from middlewared.job import Job

__all__ = ("ZFSResourceEncryptionService",)


class ZFSResourceEncryptionService(Service):
    class Config:
        namespace = "zfs.resource.encryption"
        cli_private = True

    @api_method(
        ZFSResourceEncryptionLockArgs,
        ZFSResourceEncryptionLockResult,
        roles=["ZFS_RESOURCE_WRITE"],
        audit="ZFS resource encryption lock",
        audit_extended=lambda data: data.get("path"),
        check_annotations=True,
    )
    @job(lock=DATASET_ENCRYPTION_LOCK)
    def lock(self, job: Job, data: ZFSResourceEncryptionLockArgsData) -> None:
        """
        Lock an encryption root that is encrypted with a passphrase.

        The services and shares using the resource are stopped, then the resource and its descendants are unmounted
        and the key is unloaded. The former mountpoint is made immutable so nothing can be written in its place while
        the resource is locked.

        Example:

        .. code:: json

            {"path": "tank/secure", "force_unmount": true}
        """
        self.call_sync2(self.s.zfs.resource.encryption.lock_impl, data)

    @api_method(
        ZFSResourceEncryptionUnlockArgs,
        ZFSResourceEncryptionUnlockResult,
        roles=["ZFS_RESOURCE_WRITE"],
        audit="ZFS resource encryption unlock",
        audit_extended=lambda data: data.get("path"),
        check_annotations=True,
    )
    @job(
        lock=lambda args: dataset_encryption_unlock_lock(job_args_path(args)),
        pipes=["input"],
        check_pipes=False,
    )
    def unlock(self, job: Job, data: ZFSResourceEncryptionUnlockArgsData) -> ZFSResourceEncryptionUnlockEntry:
        """
        Unlock an encryption root, and the locked encryption roots below it when ``recursive`` is set.

        Keys and passphrases are given per encryption root in ``keys``, or uploaded to the input pipe as the JSON
        file :method:`zfs.resource.encryption.export_keys` writes when ``key_file`` is set. A hex key the system has
        stored is used when none is given. Only a resource that is unlocked with a supplied hex key has that key
        stored.

        Something already present at a mount path fails the unlock unless ``force`` is set, in which case it is
        renamed aside. :method:`zfs.resource.encryption.unlock_summary` reports what an unlock would do.

        Example:

        .. code:: json

            {"path": "tank/secure", "keys": [{"path": "tank/secure", "passphrase": "correct horse battery staple"}]}
        """
        return self.call_sync2(self.s.zfs.resource.encryption.unlock_impl, job, data)

    @api_method(
        ZFSResourceEncryptionUnlockSummaryArgs,
        ZFSResourceEncryptionUnlockSummaryResult,
        roles=["ZFS_RESOURCE_READ"],
        check_annotations=True,
    )
    @job(
        lock=lambda args: dataset_encryption_unlock_summary_lock(job_args_path(args)),
        pipes=["input"],
        check_pipes=False,
    )
    def unlock_summary(
        self, job: Job, data: ZFSResourceEncryptionUnlockSummaryArgsData
    ) -> list[ZFSResourceEncryptionUnlockSummaryEntry]:
        """
        Report, for every encryption root at or below ``path``, whether an unlock with the given keys would succeed.

        Keys and passphrases are supplied as for :method:`zfs.resource.encryption.unlock` and are only checked;
        nothing is unlocked. ``valid_key`` tells whether the supplied or stored key opens the encryption root, while
        ``unlock_successful`` also accounts for a locked parent and for something already present at the mount
        path. An encryption root that is already unlocked always reports ``unlock_successful``.
        """
        return self.call_sync2(self.s.zfs.resource.encryption.unlock_summary_impl, job, data)

    @api_method(
        ZFSResourceEncryptionExportKeyArgs,
        ZFSResourceEncryptionExportKeyResult,
        roles=["ZFS_RESOURCE_WRITE"],
        audit="ZFS resource encryption export key",
        audit_extended=lambda data: data.get("path"),
        check_annotations=True,
    )
    @job(lock=DATASET_ENCRYPTION_EXPORT_KEYS_LOCK, pipes=["output"], check_pipes=False)
    def export_key(self, job: Job, data: ZFSResourceEncryptionExportKeyArgsData) -> Secret[str | None]:
        """
        Export the hex key the system stores for an encryption root.

        The key is returned, or written to the output pipe as a JSON file when ``download`` is set. Passphrases are
        never stored, so they cannot be exported.
        """
        return Secret[str | None](self.call_sync2(self.s.zfs.resource.encryption.export_key_impl, job, data))

    @api_method(
        ZFSResourceEncryptionExportKeysArgs,
        ZFSResourceEncryptionExportKeysResult,
        roles=["ZFS_RESOURCE_WRITE", "REPLICATION_TASK_WRITE"],
        audit="ZFS resource encryption export keys",
        audit_extended=lambda data: data.get("path"),
        check_annotations=True,
    )
    @job(lock=DATASET_ENCRYPTION_EXPORT_KEYS_LOCK, pipes=["output"])
    def export_keys(self, job: Job, data: ZFSResourceEncryptionExportKeysArgsData) -> None:
        """
        Export the hex keys the system stores for ``path`` and its descendants.

        The output pipe receives a JSON file mapping each encryption root to its key, which
        :method:`zfs.resource.encryption.unlock` accepts with ``key_file``. Stored keys that no longer open their
        encryption root are discarded first.
        """
        self.call_sync2(self.s.zfs.resource.encryption.export_keys_impl, job, data)

    @api_method(
        ZFSResourceEncryptionExportReplicationKeysArgs,
        ZFSResourceEncryptionExportReplicationKeysResult,
        roles=["ZFS_RESOURCE_WRITE", "REPLICATION_TASK_WRITE"],
        audit="ZFS resource encryption export replication keys",
        audit_extended=lambda data: data.get("id"),
        check_annotations=True,
    )
    @job(pipes=["output"])
    def export_replication_keys(self, job: Job, data: ZFSResourceEncryptionExportReplicationKeysArgsData) -> None:
        """
        Export the stored hex keys of a push replication task's source encryption roots.

        The output pipe receives a JSON file mapping each target path to the key of its source, ready to unlock the
        replicated resources on the destination system.
        """
        self.call_sync2(self.s.zfs.resource.encryption.export_replication_keys_impl, job, data)

    @api_method(
        ZFSResourceEncryptionChangeKeyArgs,
        ZFSResourceEncryptionChangeKeyResult,
        roles=["ZFS_RESOURCE_WRITE"],
        audit="ZFS resource encryption change key",
        audit_extended=lambda data: data.get("path"),
        check_annotations=True,
    )
    @job(
        lock=lambda args: dataset_encryption_change_key_lock(job_args_path(args)),
        pipes=["input"],
        check_pipes=False,
    )
    def change_key(self, job: Job, data: ZFSResourceEncryptionChangeKeyArgsData) -> None:
        """
        Change the key or passphrase of an unlocked encryption root.

        A hex key is stored by the system; a passphrase never is. With ``key_file`` the hex key is read from the
        input pipe.

        Switching to a passphrase is refused when an encryption root below ``path`` uses a hex key, or when ``path``
        is a pool holding the system dataset. Switching to a hex key is refused when a parent is encrypted with a
        passphrase.

        Example:

        .. code:: json

            {"path": "tank/secure", "generate_key": true}
        """
        self.call_sync2(self.s.zfs.resource.encryption.change_key_impl, job, data)

    @api_method(
        ZFSResourceEncryptionInheritArgs,
        ZFSResourceEncryptionInheritResult,
        roles=["ZFS_RESOURCE_WRITE"],
        audit="ZFS resource encryption inherit",
        audit_extended=lambda data: data.get("path"),
        check_annotations=True,
    )
    def inherit(self, data: ZFSResourceEncryptionInheritArgsData) -> None:
        """
        Make an unlocked encryption root part of its parent's encryption root, discarding its own key.

        The parent must be encrypted. When the parent's encryption root uses a passphrase, no encryption root below
        ``path`` may use a hex key.
        """
        self.call_sync2(self.s.zfs.resource.encryption.inherit_impl, data)

    @private
    @pass_thread_local_storage
    def unlock_impl(
        self, tls: Any, job: Job, data: ZFSResourceEncryptionUnlockArgsData
    ) -> ZFSResourceEncryptionUnlockEntry:
        return _lock.unlock(self.context, job, tls, data)

    @private
    @pass_thread_local_storage
    def unlock_summary_impl(
        self, tls: Any, job: Job, data: ZFSResourceEncryptionUnlockSummaryArgsData
    ) -> list[ZFSResourceEncryptionUnlockSummaryEntry]:
        return _lock.unlock_summary(self.context, job, tls, data)

    @private
    @pass_thread_local_storage
    def lock_impl(self, tls: Any, data: ZFSResourceEncryptionLockArgsData) -> None:
        _lock.lock(self.context, tls, data)

    @private
    @pass_thread_local_storage
    def export_key_impl(self, tls: Any, job: Job, data: ZFSResourceEncryptionExportKeyArgsData) -> str | None:
        return _info.export_key(self.context, job, tls, data)

    @private
    @pass_thread_local_storage
    def export_keys_impl(self, tls: Any, job: Job, data: ZFSResourceEncryptionExportKeysArgsData) -> None:
        _info.export_keys(self.context, job, tls, data)

    @private
    def export_replication_keys_impl(self, job: Job, data: ZFSResourceEncryptionExportReplicationKeysArgsData) -> None:
        _info.export_replication_keys(self.context, job, data)

    @private
    @pass_thread_local_storage
    def change_key_impl(self, tls: Any, job: Job, data: ZFSResourceEncryptionChangeKeyArgsData) -> None:
        _ops.change_key(self.context, job, tls, data)

    @private
    @pass_thread_local_storage
    def inherit_impl(self, tls: Any, data: ZFSResourceEncryptionInheritArgsData) -> None:
        _ops.inherit(self.context, tls, data)

    @private
    async def start_attachments_on_unlock(self, datasets: list[dict[str, Any]]) -> None:
        await _lock.start_attachments_on_unlock(self.context, datasets)

    @private
    def store_key(self, name: str, encryption_key: str | None, key_format: str | None) -> int | None:
        return _keys.store_key(self.context, name, encryption_key, key_format)

    @private
    def delete_keys(self, filters: list[Any]) -> None:
        _keys.delete_keys(self.context, filters)

    @private
    def stored_keys(self, filters: list[Any]) -> dict[str, str]:
        return _keys.stored_keys(self.context, filters)

    @private
    @pass_thread_local_storage
    def encryption_roots(
        self, tls: Any, path: str, state: Literal["locked", "unlocked", "all"]
    ) -> dict[str, dict[str, Any]]:
        return _info.encryption_roots(self.context, tls, path, state)

    @private
    @pass_thread_local_storage
    def encryption_state(self, tls: Any, path: str) -> dict[str, Any]:
        return _info.encryption_state(self.context, tls, path)

    @periodic(86400)
    @private
    @pass_thread_local_storage
    @job(lock=dataset_encryption_sync_keys_lock)
    def sync_keys(self, job: Job, tls: Any, name: str | None = None) -> None:
        _keys.sync_keys(self.context, tls, name)

    @private
    def replication_keys(
        self,
        task: int | ReplicationEntry,
        mapping: dict[str, list[str]] | None = None,
        skip_sync: bool = False,
    ) -> dict[str, str]:
        return _info.replication_keys(self.context, task, mapping, skip_sync)

    @private
    def encryption_root_mapping(self) -> dict[str, list[str]]:
        return _info.encryption_root_mapping(self.context)
