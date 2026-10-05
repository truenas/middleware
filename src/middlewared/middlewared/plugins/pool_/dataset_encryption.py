import errno

from pydantic import ValidationError as PydanticValidationError

from middlewared.api import api_method
from middlewared.api.current import (
    PoolDatasetChangeKeyArgs,
    PoolDatasetChangeKeyResult,
    PoolDatasetEncryptionSummaryArgs,
    PoolDatasetEncryptionSummaryResult,
    PoolDatasetExportKeyArgs,
    PoolDatasetExportKeyResult,
    PoolDatasetExportKeysArgs,
    PoolDatasetExportKeysForReplicationArgs,
    PoolDatasetExportKeysForReplicationResult,
    PoolDatasetExportKeysResult,
    PoolDatasetInheritParentEncryptionPropertiesArgs,
    PoolDatasetInheritParentEncryptionPropertiesResult,
    PoolDatasetLockArgs,
    PoolDatasetLockResult,
    PoolDatasetUnlockArgs,
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
from middlewared.service import Service, job
from middlewared.service_exception import ValidationErrors


def zr_args[T](model: type[T], **kwargs) -> T:
    try:
        return model(**kwargs)
    except PydanticValidationError as e:
        verrors = ValidationErrors()
        for err in e.errors():
            verrors.add(".".join(map(str, err["loc"])), err["msg"], errno.EINVAL)
        raise verrors


class PoolDatasetService(Service):
    class Config:
        namespace = "pool.dataset"

    @api_method(
        PoolDatasetLockArgs,
        PoolDatasetLockResult,
        roles=["DATASET_WRITE"],
        audit="Pool dataset lock",
        audit_extended=lambda id_, options=None: id_,
    )
    @job(lock="zfs_resource_encryption_lock")
    def lock(self, job, id_, options):
        """
        Locks ``id`` dataset. It will unmount the dataset and its children before locking.

        After the dataset has been unmounted, system will set immutable flag on the dataset's mountpoint where
        the dataset was mounted before it was locked making sure that the path cannot be modified. Once the dataset
        is unlocked, it will not be affected by this change and consumers can continue consuming it.

        This method is a compatibility wrapper for :method:`zfs.resource.encryption.lock`.
        """
        self.call_sync2(
            self.s.zfs.resource.encryption.lock_impl,
            zr_args(ZFSResourceEncryptionLockArgsData, path=id_, force_unmount=options["force_umount"]),
        )
        return True

    @api_method(
        PoolDatasetUnlockArgs,
        PoolDatasetUnlockResult,
        roles=["DATASET_WRITE"],
        audit="Pool dataset unlock",
        audit_extended=lambda id_, options=None: id_,
    )
    @job(lock=lambda args: f"zfs_resource_encryption_unlock_{args[0]}", pipes=["input"], check_pipes=False)
    def unlock(self, job, id_, options):
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

        This method is a compatibility wrapper for :method:`zfs.resource.encryption.unlock`.
        """
        data = zr_args(
            ZFSResourceEncryptionUnlockArgsData,
            path=id_,
            recursive=options["recursive"],
            force=options["force"],
            key_file=options["key_file"],
            keys=[
                {
                    "path": ds["name"],
                    "key": ds.get("key"),
                    "passphrase": ds.get("passphrase"),
                    "force": ds["force"],
                    "recursive": ds["recursive"],
                }
                for ds in options["datasets"]
            ],
        )
        return self.call_sync2(
            self.s.zfs.resource.encryption.unlock_body_impl,
            job,
            data.model_dump(expose_secrets=True),
            options["toggle_attachments"],
        )

    @api_method(
        PoolDatasetEncryptionSummaryArgs,
        PoolDatasetEncryptionSummaryResult,
        roles=["DATASET_READ"],
    )
    @job(lock=lambda args: f"zfs_resource_encryption_unlock_summary_{args[0]}", pipes=["input"], check_pipes=False)
    def encryption_summary(self, job, id_, options):
        """
        Retrieve summary of all encrypted roots under ``id``.

        Keys/passphrase can be supplied to check if the keys are valid.

        This method is a compatibility wrapper for :method:`zfs.resource.encryption.unlock_summary`.

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
        data = zr_args(
            ZFSResourceEncryptionUnlockSummaryArgsData,
            path=id_,
            force=options["force"],
            key_file=options["key_file"],
            keys=[
                {
                    "path": ds["name"],
                    "key": ds.get("key"),
                    "passphrase": ds.get("passphrase"),
                    "force": ds["force"],
                }
                for ds in options["datasets"]
            ],
        )
        results = []
        for entry in self.call_sync2(self.s.zfs.resource.encryption.unlock_summary_impl, job, data):
            result = entry.model_dump()
            results.append(
                {
                    "name": result.pop("path"),
                    **result,
                    "key_format": result["key_format"].upper(),
                }
            )
        return results

    @api_method(
        PoolDatasetExportKeysArgs,
        PoolDatasetExportKeysResult,
        roles=["DATASET_WRITE", "REPLICATION_TASK_WRITE"],
        audit="Pool dataset export keys",
        audit_extended=lambda id_: id_,
    )
    @job(lock="zfs_resource_encryption_export_keys", pipes=["output"])
    def export_keys(self, job, id_):
        """
        Export keys for ``id`` and its children which are stored in the system. The exported file is a JSON file
        which has a dictionary containing dataset names as keys and their keys as the value.

        Please refer to websocket documentation for downloading the file.

        This method is a compatibility wrapper for :method:`zfs.resource.encryption.export_keys`.
        """
        self.call_sync2(
            self.s.zfs.resource.encryption.export_keys_impl,
            job,
            zr_args(ZFSResourceEncryptionExportKeysArgsData, path=id_),
        )

    @api_method(
        PoolDatasetExportKeysForReplicationArgs,
        PoolDatasetExportKeysForReplicationResult,
        roles=["DATASET_WRITE", "REPLICATION_TASK_WRITE"],
        audit="Pool dataset export keys for replication",
        audit_extended=lambda task_id: task_id,
    )
    @job(pipes=["output"])
    def export_keys_for_replication(self, job, task_id):
        """
        Export keys for replication task ``id`` for source dataset(s) which are stored in the system. The exported file
        is a JSON file which has a dictionary containing dataset names as keys and their keys as the value.

        Please refer to websocket documentation for downloading the file.

        This method is a compatibility wrapper for :method:`zfs.resource.encryption.export_replication_keys`.
        """
        self.call_sync2(
            self.s.zfs.resource.encryption.export_replication_keys_impl,
            job,
            zr_args(ZFSResourceEncryptionExportReplicationKeysArgsData, id=task_id),
        )

    @api_method(
        PoolDatasetExportKeyArgs,
        PoolDatasetExportKeyResult,
        roles=["DATASET_WRITE"],
        audit="Pool dataset export key",
        audit_extended=lambda id_, download=False: id_,
    )
    @job(lock="zfs_resource_encryption_export_keys", pipes=["output"], check_pipes=False)
    def export_key(self, job, id_, download):
        """
        Export own encryption key for dataset ``id``. If ``download`` is ``true``, key will be downloaded in a json file
        where the same file can be used to unlock the dataset, otherwise it will be returned as string.

        Please refer to websocket documentation for downloading the file.

        This method is a compatibility wrapper for :method:`zfs.resource.encryption.export_key`.
        """
        return self.call_sync2(
            self.s.zfs.resource.encryption.export_key_impl,
            job,
            zr_args(ZFSResourceEncryptionExportKeyArgsData, path=id_, download=download),
        )

    @api_method(
        PoolDatasetChangeKeyArgs,
        PoolDatasetChangeKeyResult,
        roles=["DATASET_WRITE"],
        audit="Pool dataset change key",
        audit_extended=lambda id_, options=None: id_,
    )
    @job(lock=lambda args: f"zfs_resource_encryption_change_key_{args[0]}", pipes=["input"], check_pipes=False)
    def change_key(self, job, id_, options):
        """
        Change encryption properties for the ``id`` encrypted dataset.

        Changing dataset encryption to use a passphrase instead of a key is not allowed if:

        1. It has encrypted roots as children that are encrypted with a key.
        2. It is a root dataset where the system dataset is located.

        This method is a compatibility wrapper for :method:`zfs.resource.encryption.change_key`.
        """
        self.call_sync2(
            self.s.zfs.resource.encryption.change_key_impl,
            job,
            zr_args(
                ZFSResourceEncryptionChangeKeyArgsData,
                path=id_,
                generate_key=options["generate_key"],
                key_file=options["key_file"],
                pbkdf2iters=options["pbkdf2iters"],
                passphrase=options["passphrase"],
                key=options["key"],
            ),
        )

    @api_method(
        PoolDatasetInheritParentEncryptionPropertiesArgs,
        PoolDatasetInheritParentEncryptionPropertiesResult,
        roles=["DATASET_WRITE"],
        audit="Pool dataset inherit parent encryption properties",
        audit_extended=lambda id_: id_,
    )
    def inherit_parent_encryption_properties(self, id_):
        """
        Allows inheriting parent's encryption root discarding its current encryption settings. This
        can only be done where ``id`` has an encrypted parent and ``id`` itself is an encryption root.

        This method is a compatibility wrapper for :method:`zfs.resource.encryption.inherit`.
        """
        self.call_sync2(self.s.zfs.resource.encryption.inherit, zr_args(ZFSResourceEncryptionInheritArgsData, path=id_))
