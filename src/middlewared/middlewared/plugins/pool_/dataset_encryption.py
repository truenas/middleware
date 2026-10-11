from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import Secret

from middlewared.api import api_method
from middlewared.api.base import NotRequired
from middlewared.api.base.handler.accept import validate_model
from middlewared.api.current import (
    PoolDatasetChangeKeyArgs,
    PoolDatasetChangeKeyOptions,
    PoolDatasetChangeKeyResult,
    PoolDatasetEncryptionSummary,
    PoolDatasetEncryptionSummaryArgs,
    PoolDatasetEncryptionSummaryOptions,
    PoolDatasetEncryptionSummaryResult,
    PoolDatasetExportKeyArgs,
    PoolDatasetExportKeyResult,
    PoolDatasetExportKeysArgs,
    PoolDatasetExportKeysForReplicationArgs,
    PoolDatasetExportKeysForReplicationResult,
    PoolDatasetExportKeysResult,
    PoolDatasetInheritParentEncryptionPropertiesArgs,
    PoolDatasetInheritParentEncryptionPropertiesResult,
    PoolDatasetInsertOrUpdateEncryptedRecordArgs,
    PoolDatasetInsertOrUpdateEncryptedRecordResult,
    PoolDatasetLockArgs,
    PoolDatasetLockOptions,
    PoolDatasetLockResult,
    PoolDatasetUnlock,
    PoolDatasetUnlockArgs,
    PoolDatasetUnlockOptions,
    PoolDatasetUnlockResult,
    ZFSResourceEncryptionChangeKeyArgsData,
    ZFSResourceEncryptionExportKeyArgsData,
    ZFSResourceEncryptionExportKeysArgsData,
    ZFSResourceEncryptionExportReplicationKeysArgsData,
    ZFSResourceEncryptionInheritArgsData,
    ZFSResourceEncryptionLockArgsData,
    ZFSResourceEncryptionUnlockArgsData,
    ZFSResourceEncryptionUnlockSummaryArgsData,
)
from middlewared.plugins.zfs.encryption_job_locks import (
    DATASET_ENCRYPTION_EXPORT_KEYS_LOCK,
    DATASET_ENCRYPTION_LOCK,
    dataset_encryption_change_key_lock,
    dataset_encryption_unlock_lock,
    dataset_encryption_unlock_summary_lock,
)
from middlewared.service import Service, job, private

if TYPE_CHECKING:
    from middlewared.job import Job


class PoolDatasetService(Service):
    class Config:
        namespace = "pool.dataset"

    @api_method(
        PoolDatasetLockArgs,
        PoolDatasetLockResult,
        roles=["DATASET_WRITE"],
        audit="Pool dataset lock",
        audit_extended=lambda id_, options=None: id_,
        check_annotations=True,
    )
    @job(lock=DATASET_ENCRYPTION_LOCK)
    def lock(self, job: Job, id_: str, options: PoolDatasetLockOptions) -> Literal[True]:
        """
        Locks ``id`` dataset. It will unmount the dataset and its children before locking.

        After the dataset has been unmounted, system will set immutable flag on the dataset's mountpoint where
        the dataset was mounted before it was locked making sure that the path cannot be modified. Once the dataset
        is unlocked, it will not be affected by this change and consumers can continue consuming it.
        """
        self.call_sync2(
            self.s.zfs.resource.encryption.lock_impl,
            validate_model(
                ZFSResourceEncryptionLockArgsData,
                {"path": id_, "force_unmount": options.force_umount},
                dump_models=False,
            ),
        )
        return True

    @api_method(
        PoolDatasetUnlockArgs,
        PoolDatasetUnlockResult,
        roles=["DATASET_WRITE"],
        audit="Pool dataset unlock",
        audit_extended=lambda id_, options=None: id_,
        check_annotations=True,
    )
    @job(lock=lambda args: dataset_encryption_unlock_lock(args[0]), pipes=["input"], check_pipes=False)
    def unlock(self, job: Job, id_: str, options: PoolDatasetUnlockOptions) -> PoolDatasetUnlock:
        """
        Unlock dataset ``id`` (and its children if ``unlock_options.recursive`` is ``true``).

        If ``id`` is not encrypted, an exception is raised with one exception: when ``id`` is a root dataset and
        ``unlock_options.recursive`` is specified, encryption validation is not performed for ``id``. This allows
        unlocking encrypted children for the entire pool ``id``.

        There are two ways to supply the key(s)/passphrase(s) for unlocking a dataset:

        1. Upload a JSON file which contains encrypted dataset keys (it is read from the input pipe if
           ``unlock_options.key_file`` is ``true``). The format is the one used for exporting encrypted dataset
           keys (:method:`pool.dataset.export_keys`).

        2. Specify a key or a passphrase for each unlocked dataset using ``unlock_options.datasets``.
        """
        keys = []
        for ds in options.datasets:
            keys.append(
                {
                    "path": ds.name,
                    "key": None if ds.key is NotRequired else ds.key,
                    "passphrase": None if ds.passphrase is NotRequired else ds.passphrase,
                    "force": ds.force,
                    "recursive": ds.recursive,
                }
            )
        data = validate_model(
            ZFSResourceEncryptionUnlockArgsData,
            {
                "path": id_,
                "recursive": options.recursive,
                "force": options.force,
                "key_file": options.key_file,
                "start_attachments": options.toggle_attachments,
                "keys": keys,
            },
            dump_models=False,
        )
        result = self.call_sync2(self.s.zfs.resource.encryption.unlock_impl, job, data)
        return PoolDatasetUnlock(**result.model_dump())

    @api_method(
        PoolDatasetEncryptionSummaryArgs,
        PoolDatasetEncryptionSummaryResult,
        roles=["DATASET_READ"],
        check_annotations=True,
    )
    @job(lock=lambda args: dataset_encryption_unlock_summary_lock(args[0]), pipes=["input"], check_pipes=False)
    def encryption_summary(
        self, job: Job, id_: str, options: PoolDatasetEncryptionSummaryOptions
    ) -> list[PoolDatasetEncryptionSummary]:
        """
        Retrieve summary of all encrypted roots under ``id``.

        Keys/passphrase can be supplied to check if the keys are valid.

        Example output::

            [
                {
                    "name": "vol",
                    "key_format": "PASSPHRASE",
                    "key_present_in_database": false,
                    "valid_key": true,
                    "locked": true,
                    "unlock_error": null,
                    "unlock_successful": true
                },
                {
                    "name": "vol/c1/d1",
                    "key_format": "PASSPHRASE",
                    "key_present_in_database": false,
                    "valid_key": false,
                    "locked": true,
                    "unlock_error": "Provided key is invalid",
                    "unlock_successful": false
                },
                {
                    "name": "vol/c",
                    "key_format": "PASSPHRASE",
                    "key_present_in_database": false,
                    "valid_key": false,
                    "locked": true,
                    "unlock_error": "Key not provided",
                    "unlock_successful": false
                },
                {
                    "name": "vol/c/d2",
                    "key_format": "PASSPHRASE",
                    "key_present_in_database": false,
                    "valid_key": false,
                    "locked": true,
                    "unlock_error": "Child cannot be unlocked when parent \"vol/c\" is locked and key is invalid",
                    "unlock_successful": false
                }
            ]
        """
        keys = []
        for ds in options.datasets:
            keys.append(
                {
                    "path": ds.name,
                    "key": None if ds.key is NotRequired else ds.key,
                    "passphrase": None if ds.passphrase is NotRequired else ds.passphrase,
                    "force": ds.force,
                }
            )
        data = validate_model(
            ZFSResourceEncryptionUnlockSummaryArgsData,
            {"path": id_, "force": options.force, "key_file": options.key_file, "keys": keys},
            dump_models=False,
        )
        results = []
        for entry in self.call_sync2(self.s.zfs.resource.encryption.unlock_summary_impl, job, data):
            results.append(
                PoolDatasetEncryptionSummary(
                    name=entry.path,
                    key_format=entry.key_format.upper(),
                    key_present_in_database=entry.key_present_in_database,
                    valid_key=entry.valid_key,
                    locked=entry.locked,
                    unlock_error=entry.unlock_error,
                    unlock_successful=entry.unlock_successful,
                )
            )
        return results

    @api_method(
        PoolDatasetExportKeysArgs,
        PoolDatasetExportKeysResult,
        roles=["DATASET_WRITE", "REPLICATION_TASK_WRITE"],
        audit="Pool dataset export keys",
        audit_extended=lambda id_: id_,
        check_annotations=True,
    )
    @job(lock=DATASET_ENCRYPTION_EXPORT_KEYS_LOCK, pipes=["output"])
    def export_keys(self, job: Job, id_: str) -> None:
        """
        Export keys for ``id`` and its children which are stored in the system. The exported file is a JSON file
        which has a dictionary containing dataset names as keys and their keys as the value.

        Please refer to websocket documentation for downloading the file.
        """
        self.call_sync2(
            self.s.zfs.resource.encryption.export_keys_impl,
            job,
            validate_model(ZFSResourceEncryptionExportKeysArgsData, {"path": id_}, dump_models=False),
        )

    @api_method(
        PoolDatasetExportKeysForReplicationArgs,
        PoolDatasetExportKeysForReplicationResult,
        roles=["DATASET_WRITE", "REPLICATION_TASK_WRITE"],
        audit="Pool dataset export keys for replication",
        audit_extended=lambda task_id: task_id,
        check_annotations=True,
    )
    @job(pipes=["output"])
    def export_keys_for_replication(self, job: Job, task_id: int) -> None:
        """
        Export keys for replication task ``id`` for source dataset(s) which are stored in the system. The exported file
        is a JSON file which has a dictionary containing dataset names as keys and their keys as the value.

        Please refer to websocket documentation for downloading the file.
        """
        self.call_sync2(
            self.s.zfs.resource.encryption.export_replication_keys_impl,
            job,
            validate_model(ZFSResourceEncryptionExportReplicationKeysArgsData, {"id": task_id}, dump_models=False),
        )

    @api_method(
        PoolDatasetExportKeyArgs,
        PoolDatasetExportKeyResult,
        roles=["DATASET_WRITE"],
        audit="Pool dataset export key",
        audit_extended=lambda id_, download=False: id_,
        check_annotations=True,
    )
    @job(lock=DATASET_ENCRYPTION_EXPORT_KEYS_LOCK, pipes=["output"], check_pipes=False)
    def export_key(self, job: Job, id_: str, download: bool) -> Secret[str | None]:
        """
        Export own encryption key for dataset ``id``. If ``download`` is ``true``, key will be downloaded in a json file
        where the same file can be used to unlock the dataset, otherwise it will be returned as string.

        Please refer to websocket documentation for downloading the file.
        """
        key = self.call_sync2(
            self.s.zfs.resource.encryption.export_key_impl,
            job,
            validate_model(
                ZFSResourceEncryptionExportKeyArgsData, {"path": id_, "download": download}, dump_models=False
            ),
        )
        return Secret[str | None](key)

    @api_method(
        PoolDatasetChangeKeyArgs,
        PoolDatasetChangeKeyResult,
        roles=["DATASET_WRITE"],
        audit="Pool dataset change key",
        audit_extended=lambda id_, options=None: id_,
        check_annotations=True,
    )
    @job(lock=lambda args: dataset_encryption_change_key_lock(args[0]), pipes=["input"], check_pipes=False)
    def change_key(self, job: Job, id_: str, options: PoolDatasetChangeKeyOptions) -> None:
        """
        Change encryption properties for the ``id`` encrypted dataset.

        Changing dataset encryption to use a passphrase instead of a key is not allowed if:

        1. It has encrypted roots as children that are encrypted with a key.
        2. It is a root dataset where the system dataset is located.
        """
        self.call_sync2(
            self.s.zfs.resource.encryption.change_key_impl,
            job,
            validate_model(
                ZFSResourceEncryptionChangeKeyArgsData,
                {
                    "path": id_,
                    "generate_key": options.generate_key,
                    "key_file": options.key_file,
                    "pbkdf2iters": options.pbkdf2iters,
                    "passphrase": options.passphrase,
                    "key": options.key,
                },
                dump_models=False,
            ),
        )

    @api_method(
        PoolDatasetInheritParentEncryptionPropertiesArgs,
        PoolDatasetInheritParentEncryptionPropertiesResult,
        roles=["DATASET_WRITE"],
        audit="Pool dataset inherit parent encryption properties",
        audit_extended=lambda id_: id_,
        check_annotations=True,
    )
    def inherit_parent_encryption_properties(self, id_: str) -> None:
        """
        Allows inheriting parent's encryption root discarding its current encryption settings. This
        can only be done where ``id`` has an encrypted parent and ``id`` itself is an encryption root.
        """
        self.call_sync2(
            self.s.zfs.resource.encryption.inherit_impl,
            validate_model(ZFSResourceEncryptionInheritArgsData, {"path": id_}, dump_models=False),
        )

    # Replication sources call this on the target over midclt, so it must keep accepting this payload.
    @private
    @api_method(
        PoolDatasetInsertOrUpdateEncryptedRecordArgs,
        PoolDatasetInsertOrUpdateEncryptedRecordResult,
        roles=["DATASET_WRITE"],
        check_annotations=True,
    )
    def insert_or_update_encrypted_record(self, data: PoolDatasetInsertOrUpdateEncryptedRecordArgs) -> int | None:
        key_format = data.key_format.lower() if data.key_format else None
        return self.call_sync2(self.s.zfs.resource.encryption.store_key, data.name, data.encryption_key, key_format)
