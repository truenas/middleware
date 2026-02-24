from __future__ import annotations

import errno
import os
import pathlib
import threading
from typing import TYPE_CHECKING, Callable, Literal

from truenas_pylibzfs import ZFSError, ZFSException, ZFSType

if TYPE_CHECKING:
    from middlewared.common.attachment import FSAttachmentDelegate
    from middlewared.job import Job

from middlewared.api import api_method
from middlewared.api.current import (
    PoolAttachment,
    PoolDatasetEntry,
    PoolDatasetChangeKeyOptions,
    PoolDatasetChecksumChoices,
    PoolDatasetEncryptionAlgorithmChoices,
    PoolDatasetEncryptionSummary,
    PoolDatasetEncryptionSummaryOptions,
    PoolDatasetInsertOrUpdateEncryptedRecordData,
    PoolDatasetLockOptions,
    PoolDatasetUnlockOptions,
    PoolDatasetAttachmentsArgs, PoolDatasetAttachmentsResult,
    PoolDatasetChangeKeyArgs, PoolDatasetChangeKeyResult,
    PoolDatasetChecksumChoicesArgs, PoolDatasetChecksumChoicesResult,
    PoolDatasetCompressionChoicesArgs, PoolDatasetCompressionChoicesResult,
    PoolDatasetCreateArgs, PoolDatasetCreateResult, PoolDatasetCreateFilesystem, PoolDatasetCreateVolume,
    PoolDatasetUpdateArgs, PoolDatasetUpdateResult, PoolDatasetUpdate,
    PoolDatasetDeleteArgs, PoolDatasetDeleteResult,
    PoolDatasetEncryptionAlgorithmChoicesArgs, PoolDatasetEncryptionAlgorithmChoicesResult,
    PoolDatasetDetailsArgs, PoolDatasetDetailsResult,
    PoolDatasetEncryptionSummaryArgs, PoolDatasetEncryptionSummaryResult,
    PoolDatasetExportKeyArgs, PoolDatasetExportKeyResult,
    PoolDatasetExportKeysArgs, PoolDatasetExportKeysResult,
    PoolDatasetExportKeysForReplicationArgs, PoolDatasetExportKeysForReplicationResult,
    PoolDatasetGetQuotaArgs, PoolDatasetGetQuotaResult,
    PoolDatasetInheritParentEncryptionPropertiesArgs, PoolDatasetInheritParentEncryptionPropertiesResult,
    PoolDatasetInsertOrUpdateEncryptedRecordArgs, PoolDatasetInsertOrUpdateEncryptedRecordResult,
    PoolDatasetLockArgs, PoolDatasetLockResult,
    PoolDatasetProcessesArgs, PoolDatasetProcessesResult,
    PoolDatasetRecommendedZvolBlocksizeArgs, PoolDatasetRecommendedZvolBlocksizeResult,
    PoolDatasetRecordsizeChoicesArgs, PoolDatasetRecordsizeChoicesResult,
    PoolDatasetSetQuotaArgs, PoolDatasetSetQuotaResult,
    PoolDatasetUnlockArgs, PoolDatasetUnlockResult,
    PoolDatasetPromoteArgs, PoolDatasetPromoteResult,
    PoolDatasetRenameArgs, PoolDatasetRenameResult,
    QueryFilters, QueryOptions,
    ZFSResourceQuery,
)
from middlewared.plugins.container.utils import CONTAINER_DS_NAME
from middlewared.plugins.zfs_.validation_utils import validate_dataset_name
from middlewared.plugins.zfs.utils import has_internal_path
from middlewared.service import (
    CallError, CRUDService, InstanceNotFound, job, periodic, private, ValidationError, ValidationErrors,
    filterable_api_method,
)
from middlewared.service.decorators import pass_thread_local_storage
import middlewared.sqlalchemy as sa
from middlewared.utils import BOOT_POOL_NAME_VALID
from middlewared.utils.filter_list import filter_list

from .dataset import (
    get_instance_quick, common_validation, create_impl,
    do_create, update_impl, update, do_delete, promote, rename
)
from .dataset_attachments import (
    attachments_impl, attachments_with_path,
    stop_attachment_delegates_impl,
    get_attachment_delegates_for_start, get_attachment_delegates_for_stop,
)
from .dataset_details import details_impl
from .dataset_encryption_info import (
    encryption_summary_impl, sync_db_keys_impl, path_in_locked_datasets,
    query_encrypted_roots_keys, query_encrypted_datasets,
    export_keys_impl, export_keys_for_replication_impl, export_keys_for_replication_internal,
    dataset_encryption_root_mapping_impl, export_key_impl,
)
from .dataset_encryption_lock import lock_impl, unlock_impl, unlock_handle_attachments
from .dataset_encryption_operations import (
    insert_or_update_encrypted_record, delete_encrypted_datasets_from_db,
    validate_encryption_data, change_key_impl, inherit_parent_encryption_properties_impl,
)
from .dataset_info import recommended_zvol_blocksize_impl
from .dataset_processes import processes_impl, kill_processes, processes_using_paths
from .dataset_quota import (
    query_for_quota_alert, get_quota_impl, get_quota, set_quota_impl, set_quota,
)
from .dataset_recordsize import recordsize_choices_impl
from .dataset_query_utils import generic_query
from .utils import (
    CreateImplArgs,
    CreateImplArgsDataclass,
    dataset_mountpoint,
    get_dataset_parents,
    POOL_DS_CREATE_PROPERTIES,
    POOL_DS_UPDATE_PROPERTIES,
    UpdateImplArgs,
    UpdateImplArgsDataclass,
    ZFSKeyFormat,
    ZFS_CHECKSUM_CHOICES,
    ZFS_COMPRESSION_ALGORITHM_CHOICES,
    ZFS_ENCRYPTION_ALGORITHM_CHOICES,
    ZFS_VOLUME_BLOCK_SIZE_CHOICES
)


class PoolDatasetEncryptionModel(sa.Model):
    __tablename__ = 'storage_encrypteddataset'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(255))
    encryption_key = sa.Column(sa.EncryptedText(), nullable=True)
    kmip_uid = sa.Column(sa.String(255), nullable=True, default=None)


class PoolDatasetService(CRUDService[PoolDatasetEntry]):

    class Config:
        cli_namespace = 'storage.dataset'
        datastore_primary_key_type = 'string'
        event_send = False
        namespace = 'pool.dataset'
        role_prefix = 'DATASET'
        role_separate_delete = True
        entry = PoolDatasetEntry
        generic = True

    def __init__(self, middleware):
        super().__init__(middleware)
        self.attachment_delegates: list[FSAttachmentDelegate] = []

    @private
    async def get_instance_quick(self, name: str, options: dict | None = None) -> PoolDatasetEntry:
        """Get dataset instance with minimal properties."""
        return await get_instance_quick(self.context, name, **(options or {}))

    @private
    async def internal_datasets_filters(self) -> list[list]:
        """Get filters that ensure we don't match an internal dataset."""
        return [
            ['pool', 'nin', BOOT_POOL_NAME_VALID],
            ['id', 'rnin', '/.system'],
            ['id', 'rnin', '/ix-applications/'],
            ['id', 'rnin', '/ix-apps'],
        ]

    @private
    async def is_internal_dataset(self, dataset: str) -> bool:
        """Check if a dataset is internal (boot pool, system, or apps)."""
        pool = dataset.split('/')[0]
        return not filter_list([{'id': dataset, 'pool': pool}], await self.internal_datasets_filters())

    @filterable_api_method(
        item=PoolDatasetEntry,
        pass_thread_local_storage=True,
        check_annotations=True
    )
    def query(self, tls: threading.local, filters: QueryFilters, options: QueryOptions) -> list[PoolDatasetEntry] | PoolDatasetEntry | int:
        """
        Query Pool Datasets with `query-filters` and `query-options`.

        We provide two ways to retrieve datasets. The first is a flat structure (default), where
        all datasets in the system are returned as separate objects which contain all data
        there is for their children. This retrieval type is slightly slower because of duplicates in each object.
        The second type is hierarchical, where only top level datasets are returned in the list. They contain all the
        children in the `children` key. This retrieval type is slightly faster.
        These options are controlled by the `query-options.extra.flat` attribute (default true).

        In some cases it might be desirable to only retrieve details of a dataset itself and not it's children, in this
        case `query-options.extra.retrieve_children` should be explicitly specified and set to `false` which will
        result in children not being retrieved.

        In case only some properties are desired to be retrieved for datasets, consumer should specify
        `query-options.extra.properties` which when `null` ( which is the default ) will retrieve all properties
        and otherwise a list can be specified like `["type", "used", "available"]` to retrieve selective properties.
        If no properties are desired, in that case an empty list should be sent. It should be noted that specifying
        empty list will still retrieve user properties. If user properties are not desired, in that case
        `query-options.extra.retrieve_user_props` should be set to `false`.

        `query-options.extra.snapshots` can be set to retrieve snapshot(s) of dataset in question.

        `query-options.extra.snapshots_recursive` can be set to retrieve snapshot(s) recursively of dataset in question.
        If `query-options.extra.snapshots_recursive` and `query-options.extra.snapshots` are set, snapshot(s) will be
        retrieved recursively.

        `query-options.extra.snapshots_properties` can be specified to list out properties which should be retrieved
        for snapshot(s) related to each dataset. By default only name of the snapshot would be retrieved, however
        if `null` is specified all properties of the snapshot would be retrieved in this case.
        """
        opts = options.model_dump()
        return generic_query(
            tls.lzh.iter_root_filesystems,
            filters,
            opts,
            opts.pop('extra', {})
        )

    @private
    @pass_thread_local_storage
    def create_impl(self, tls: threading.local, data: CreateImplArgs) -> None:
        # Convert TypedDict to dataclass to handle defaults for missing fields
        args = CreateImplArgsDataclass(
            name=data['name'],
            ztype=data['ztype'],
            zprops=data.get('zprops', {}),
            uprops=data.get('uprops', None),
            encrypt=data.get('encrypt', None),
            create_ancestors=data.get('create_ancestors', False)
        )

        kwargs = {"name": args.name, "type": None}
        if args.ztype == "FILESYSTEM":
            kwargs["type"] = ZFSType.ZFS_TYPE_FILESYSTEM
            if "xattr" not in args.zprops:
                # its important to set this as "sa"
                # for performance reasons
                args.zprops["xattr"] = "sa"
        elif args.ztype == "VOLUME":
            kwargs["type"] = ZFSType.ZFS_TYPE_VOLUME
            sparse = args.zprops.pop("sparse", None)  # not a real zfs property
            if sparse is True:
                # sparse volume is only created if user explicitly
                # requests it
                args.zprops["refreservation"] = "none"
            else:
                # otherwise, we always create "thick" provisioned volumes
                args.zprops.setdefault("refreservation", args.zprops["volsize"])
        else:
            raise CallError(f"Invalid dataset type: {args.ztype!r}")

        if args.zprops:
            kwargs["properties"] = args.zprops

        if args.uprops:
            kwargs["user_properties"] = args.uprops

        if args.encrypt and args.encrypt.get("encryption") != "off":
            kwargs["crypto"] = tls.lzh.resource_cryptography_config(
                keyformat=args.encrypt["keyformat"],
                key=args.encrypt["key"],
            )
            if pb := args.encrypt.get("pbkdf2iters"):
                if "properties" in kwargs:
                    kwargs["properties"]["pbkdf2iters"] = str(pb)
                else:
                    kwargs["properties"] = {"pbkdf2iters": str(pb)}

        if args.create_ancestors:
            # If we need to create ancestors, we need to handle this differently
            # truenas_pylibzfs doesn't have a direct create_ancestors flag
            # So we'll create parent datasets first if needed
            for parent in reversed(pathlib.Path(kwargs["name"]).parents):
                pp = parent.as_posix()
                if pp == "." or "/" not in pp:
                    # cwd or root dataset
                    continue
                try:
                    tls.lzh.create_resource(name=pp, type=ZFSType.ZFS_TYPE_FILESYSTEM)
                except ZFSException as e:
                    if e.code == ZFSError.EZFS_EXISTS:
                        continue
                    else:
                        raise e from None

        try:
            tls.lzh.create_resource(**kwargs)
        except Exception as e:
            raise CallError(f"Failed to create dataset {kwargs['name']}: {e}")

        mntpnt = args.zprops.get('mountpoint', '')
        if mntpnt == 'legacy' or args.zprops.get('canmount', 'on') != 'on':
            return
        elif args.name == CONTAINER_DS_NAME and mntpnt.startswith(f'/{CONTAINER_DS_NAME}'):
            self.call_sync2(
                self.s.zfs.resource.mount,
                args.name,
                mountpoint=f'/mnt{mntpnt}',  # FIXME: altroot not respected cf. NAS-138287
                recursive=args.create_ancestors,
            )
        else:
            self.call_sync2(
                self.s.zfs.resource.mount,
                args.name,
                recursive=args.create_ancestors,
            )

    @api_method(
        PoolDatasetCreateArgs,
        PoolDatasetCreateResult,
        audit='Pool dataset create',
        audit_extended=lambda data: data['name'],
        check_annotations=True
    )
    async def do_create(self, data: PoolDatasetCreateFilesystem | PoolDatasetCreateVolume) -> PoolDatasetEntry:
        """
        Creates a dataset/zvol.

        .. examples(websocket)::

          Create a dataset within tank pool.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.dataset.create,
                "params": [{
                    "name": "tank/myuser",
                    "comments": "Dataset for myuser"
                }]
            }
        """
        verrors = ValidationErrors()
        acl_to_set = None

        if '/' not in data.name:
            verrors.add('pool_dataset_create.name', 'You need a full name, e.g. pool/newdataset')
        elif not validate_dataset_name(data.name):
            verrors.add('pool_dataset_create.name', 'Invalid dataset name')
        elif data.name[-1] == ' ':
            verrors.add(
                'pool_dataset_create.name',
                'Trailing spaces are not permitted in dataset names'
            )
        else:
            parent_name = data.name.rsplit('/', 1)[0]
            if data.create_ancestors:
                # If we want to create ancestors, let's just ensure that we have at least one parent which exists
                while not await self.middleware.call(
                    'pool.dataset.query',
                    [['id', '=', parent_name]], {
                        'extra': {'retrieve_children': False, 'properties': []}
                    }
                ):
                    if '/' not in parent_name:
                        # Root dataset / pool does not exist
                        break
                    parent_name = parent_name.rsplit('/', 1)[0]

            parent_ds = await self.middleware.call(
                'pool.dataset.query',
                [('id', '=', parent_name)],
                {'extra': {'retrieve_children': False}}
            )

            if data.type == 'FILESYSTEM':
                match data.share_type:
                    case 'SMB':
                        data.casesensitivity = 'INSENSITIVE'
                        data.acltype = 'NFSV4'
                        data.aclmode = 'RESTRICTED'
                    case 'APPS' | 'MULTIPROTOCOL' | 'NFS':
                        data.casesensitivity = 'SENSITIVE'
                        data.atime = 'OFF'
                        data.acltype = 'NFSV4'
                        data.aclmode = 'PASSTHROUGH'

            await common_validation(self.context, verrors, 'pool_dataset_create', data, 'CREATE', parent_ds)

        verrors.check()

        parent_ds = parent_ds[0]
        if parent_ds['type'] == 'VOLUME':
            verrors.add(
                'pool_dataset_create.name',
                f'{parent_ds["name"]}: parent may not be a ZFS volume'
            )

        parent_mp = parent_ds['mountpoint']
        if parent_ds['locked'] or not parent_mp:
            parent_st = {'acl': False}
        else:
            parent_st = await self.middleware.call('filesystem.stat', parent_mp)
            parent_st['acltype'] = await self.middleware.call('filesystem.path_get_acltype', parent_mp)

        mountpoint = os.path.join('/mnt', data.name)

        try:
            await self.middleware.call('filesystem.stat', mountpoint)
            verrors.add('pool_dataset_create.name', f'Path {mountpoint} already exists')
        except CallError as e:
            if e.errno != errno.ENOENT:
                raise

        if data.type == 'FILESYSTEM':
            if data.share_type == 'SMB':
                if parent_st['acl'] and parent_st['acltype'] == 'NFS4':
                    acl_to_set = await self.middleware.call('filesystem.get_inherited_acl', {
                        'path': os.path.join('/mnt', parent_name),
                    })
                else:
                    acl_to_set = (await self.middleware.call('filesystem.acltemplate.by_path', {
                        'query-filters': [('name', '=', 'NFS4_RESTRICTED')],
                        'format-options': {'canonicalize': True, 'ensure_builtins': True},
                    }))[0]['acl']
            elif data.share_type == 'APPS':
                must_add_apps = True
                if parent_st['acl'] and parent_st['acltype'] == 'NFS4':
                    acl_to_set = await self.middleware.call('filesystem.get_inherited_acl', {
                        'path': os.path.join('/mnt', parent_name),
                    })

                    # The inherited ACL may already contain an entry granting MODIFY permissions.
                    # if it does, then we can skip adding the apps entry.
                    for entry in acl_to_set:
                        if entry['id'] == 568 and entry['tag'] == 'USER' and entry['type'] == 'ALLOW':
                            if entry['flags']['FILE_INHERIT'] and entry['flags']['DIRECTORY_INHERIT']:
                                if all(
                                    entry['perms'][role]
                                    for role in (
                                        'READ_DATA', 'WRITE_DATA', 'DELETE', 'DELETE_CHILD', 'READ_ACL', 'APPEND_DATA',
                                        'READ_NAMED_ATTRS', 'WRITE_NAMED_ATTRS', 'READ_ATTRIBUTES', 'WRITE_ATTRIBUTES'
                                    )
                                ):
                                    must_add_apps = False
                                    break
                else:
                    acl_to_set = (await self.middleware.call('filesystem.acltemplate.by_path', {
                        'query-filters': [('name', '=', 'NFS4_RESTRICTED')],
                        'format-options': {'canonicalize': True, 'ensure_builtins': True},
                    }))[0]['acl']

                if must_add_apps:
                    acl_to_set.append({
                        'tag': 'USER',
                        'id': 568,
                        'perms': {'BASIC': 'MODIFY'},
                        'flags': {'BASIC': 'INHERIT'},
                        'type': 'ALLOW'
                    })
            elif data.share_type in ('MULTIPROTOCOL', 'NFS'):
                if parent_st['acl'] and parent_st['acltype'] == 'NFS4':
                    acl_to_set = await self.middleware.call('filesystem.get_inherited_acl', {
                        'path': os.path.join('/mnt', parent_name),
                    })

        if acl_to_set:
            try:
                await self.middleware.call(
                    'filesystem.check_acl_execute',
                    mountpoint, acl_to_set, -1, -1
                )
            except CallError as e:
                if e.errno != errno.EPERM:
                    raise

                verrors.add('pool_dataset_create.share_type', e.errmsg)

        if data.type == 'FILESYSTEM' and data.get('acltype', 'INHERIT') != 'INHERIT':
            data['aclinherit'] = 'PASSTHROUGH' if data.acltype == 'NFSV4' else 'DISCARD'

        if parent_ds['locked']:
            verrors.add(
                'pool_dataset_create.name',
                f'{data.name.rsplit("/", 1)[0]} must be unlocked to create {data.name}.'
            )

        encryption_dict = {}
        inherit_encryption_properties = data.pop('inherit_encryption')
        if not inherit_encryption_properties:
            encryption_dict = {'encryption': 'off'}

        unencrypted_parent = False
        for parent in get_dataset_parents(data.name):
            try:
                check_ds = await self.middleware.call('pool.dataset.get_instance_quick', parent, {'encryption': True})
            except InstanceNotFound:
                continue

            if check_ds['encrypted']:
                if unencrypted_parent:
                    verrors.add(
                        'pool_dataset_create.name',
                        'Creating an encrypted dataset within an unencrypted dataset is not allowed. '
                        f'In this case, {unencrypted_parent!r} must be moved to an unencrypted dataset.'
                    )
                    break
                elif data.encryption is False and not inherit_encryption_properties:
                    # This was a design decision when native zfs encryption support was added to provide
                    # a simple straight workflow not allowing end users to create unencrypted datasets
                    # within an encrypted dataset.
                    verrors.add(
                        'pool_dataset_create.encryption',
                        f'Cannot create an unencrypted dataset within an encrypted dataset ({parent}).'
                    )
                    break
            else:
                # The unencrypted parent story is pool/encrypted/unencrypted/new_ds so in this case
                # we want to make sure user does not specify inherit encryption as it will lead to new_ds
                # not getting encryption props from pool/encrypted.
                unencrypted_parent = parent

        if data.encryption:
            if inherit_encryption_properties:
                verrors.add('pool_dataset_create.inherit_encryption', 'Must be disabled when encryption is enabled.')

            if not data.encryption_options.passphrase:
                # We want to ensure that we don't have any parent for this dataset which is encrypted with PASSPHRASE
                # because we don't allow children to be unlocked while parent is locked
                parent_encryption_root = parent_ds['encryption_root']
                if (
                    parent_encryption_root and ZFSKeyFormat(
                        (await self.get_instance(parent_encryption_root))['key_format']['value']
                    ) == ZFSKeyFormat.PASSPHRASE
                ):
                    verrors.add(
                        'pool_dataset_create.encryption',
                        'Passphrase encrypted datasets cannot have children encrypted with a key.'
                    )

        encryption_dict = await self.middleware.call(
            'pool.dataset.validate_encryption_data', None, verrors,
            {'enabled': data.pop('encryption'), **data.pop('encryption_options'), 'key_file': False},
            'pool_dataset_create.encryption_options',
        ) or encryption_dict
        verrors.check()

        if data.type == 'VOLUME':
            p_special_small_block_size = parent_ds['special_small_block_size']['parsed']
            if (
                p_special_small_block_size and data.get('special_small_block_size', 'INHERIT') == 'INHERIT'
                and ZFS_VOLUME_BLOCK_SIZE_CHOICES[data.volblocksize] < p_special_small_block_size
            ):
                data.special_small_block_size = 0

        zprops, uprops = {}, {}
        for i in POOL_DS_CREATE_PROPERTIES:
            if (
                not hasattr(data, i.api_name)
                or (i.inheritable and (api_name := getattr(data, i.api_name)) == 'INHERIT')
            ):
                continue

            if i.transform:
                api_name = i.transform(api_name)

            if i.is_user_prop:
                uprops[i.real_name] = api_name
            else:
                zprops[i.real_name] = api_name

        await self.middleware.call(
            'pool.dataset.create_impl',
            CreateImplArgs(
                name=data.name,
                ztype=data.type,
                zprops=zprops,
                uprops=uprops,
                encrypt=encryption_dict,
                create_ancestors=data.create_ancestors
            )
        )
        dataset_data = {
            'name': data.name, 'encryption_key': encryption_dict.get('key'),
            'key_format': encryption_dict.get('keyformat')
        }
        await self.middleware.call('pool.dataset.insert_or_update_encrypted_record', dataset_data)
        await self.middleware.call_hook('dataset.post_create', {'encrypted': bool(encryption_dict), **dataset_data})

        created_ds = await self.get_instance(data.name)

        if acl_to_set:
            # We're potentially auto-inheriting an ACL containing nested
            # security groups and so we need to skip the ACL validation
            acl_job = await self.middleware.call('filesystem.setacl', {
                'path': mountpoint,
                'dacl': acl_to_set,
                'options': {'validate_effective_acl': False}
            })
            await acl_job.wait(raise_error=True)

        self.middleware.send_event('pool.dataset.query', 'ADDED', id=data.name, fields=created_ds)
        return created_ds

    @private
    @pass_thread_local_storage
    def update_impl(self, tls, data: UpdateImplArgs):
        # Convert TypedDict to dataclass to handle defaults for missing fields
        args = UpdateImplArgsDataclass(
            name=data['name'],
            zprops=data.get('zprops', {}),
            uprops=data.get('uprops', {}),
            iprops=data.get('iprops', set())
        )

        ds = tls.lzh.open_resource(name=args.name)
        if args.zprops:
            ds.set_properties(properties=args.zprops)
        if args.uprops:
            ds.set_user_properties(user_properties=args.uprops)
        for i in args.iprops:
            ds.inherit_property(property=i)

    @api_method(PoolDatasetUpdateArgs, PoolDatasetUpdateResult, audit='Pool dataset update', audit_callback=True)
    async def do_update(self, audit_callback: Callable[[str], ...], id_: str, data: PoolDatasetUpdate) -> PoolDatasetEntry:
        """
        Updates a dataset/zvol `id`.

        .. examples(websocket)::

          Update the `comments` for "tank/myuser".

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.dataset.update,
                "params": ["tank/myuser", {
                    "comments": "Dataset for myuser, UPDATE #1"
                }]
            }
        """
        return await update(self.context, audit_callback, id_, data)

    @api_method(PoolDatasetDeleteArgs, PoolDatasetDeleteResult, audit='Pool dataset delete', audit_callback=True)
    async def do_delete(self, audit_callback, id_, options):
        """
        Delete dataset/zvol `id`.

        .. examples(websocket)::

          Delete "tank/myuser" dataset.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.dataset.delete",
                "params": ["tank/myuser"]
            }
        """
        if has_internal_path(id_):
            raise ValidationError('pool.dataset.delete', f'{id_} is an invalid location')

        if not options['recursive']:
            ds = await self.call2(
                self.s.zfs.resource.query_impl,
                ZFSResourceQuery(paths=[id_], properties=None, get_children=True)
            )
            if len(ds) > 1:
                raise CallError(
                    f'Failed to delete dataset: cannot destroy {id_!r}: filesystem has children', errno.ENOTEMPTY
                )

        dataset = await self.get_instance(id_)
        audit_callback(dataset['name'])
        if mountpoint := dataset_mountpoint(dataset):
            for delegate in await self.middleware.call('pool.dataset.get_attachment_delegates_for_stop'):
                attachments = await delegate.query(mountpoint, True)
                if attachments:
                    await delegate.delete(attachments)

        if dataset['locked'] and mountpoint and os.path.exists(mountpoint):
            # We would like to remove the immutable flag in this case so that it's mountpoint can be
            # cleaned automatically when we delete the dataset
            await self.middleware.call('filesystem.set_zfs_attributes', {
                'path': mountpoint,
                'zfs_file_attributes': {'immutable': False}
            })

        await self.call2(
            self.s.zfs.resource.destroy_impl, id_, recursive=options['recursive']
        )
        return True

    @api_method(PoolDatasetPromoteArgs, PoolDatasetPromoteResult, roles=['DATASET_WRITE'])
    async def promote(self, id_):
        """Promote a cloned dataset."""
        return await self.call2(self.s.zfs.resource.promote, id_)

    @api_method(
        PoolDatasetRenameArgs,
        PoolDatasetRenameResult,
        audit='Pool dataset rename from',
        audit_extended=lambda id_, options: f'{id_!r} to {options["new_name"]!r}',
        roles=['DATASET_WRITE']
    )
    async def rename(self, id_, options):
        """
        Rename a zfs resource (filesystem, snapshot, or zvolume) of `id`.

        No safety checks are performed when renaming ZFS resources. If the dataset is in use by services such
        as SMB, iSCSI, snapshot tasks, replication, or cloud sync, renaming may cause disruptions or service failures.

        Proceed only if you are certain the ZFS resource is not in use and fully understand the risks.
        Set Force to continue.

        NOTE: The "recursive" option is only valid for renaming snapshots. If True, and a snapshot is given, the \
        snapshot will be renamed recursively for all children. For example: dozer/a@now, dozer/a/b@now will be \
        renamed to dozer/a@new dozer/a/b@new. Renaming snapshots IS NOT recommended and can cause disruptions or \
        service failures all the same.
        """
        if not options['force']:
            raise ValidationError(
                'pool.dataset.rename.force',
                'No safety checks are performed when renaming ZFS resources; this may break existing usages. '
                'If you understand the risks, please set force and proceed.'
            )
        return await self.call2(
            self.s.zfs.resource.rename,
            id_,
            options['new_name'],
            options['recursive'],
            False,  # no_unmount
            options['force'],
        )

    @api_method(
        PoolDatasetDetailsArgs,
        PoolDatasetDetailsResult,
        roles=['DATASET_READ'],
        check_annotations=True,
    )
    def details(self) -> list[dict]:
        """
        Retrieve all dataset(s) details outlining any
        services/tasks which might be consuming them.
        """
        return details_impl(self.context)

    @api_method(
        PoolDatasetAttachmentsArgs,
        PoolDatasetAttachmentsResult,
        roles=['DATASET_READ'],
        check_annotations=True,
    )
    async def attachments(self, oid: str) -> list[PoolAttachment]:
        """
        Return a list of services dependent of this dataset.

        Responsible for telling the user whether there is a related
        share, asking for confirmation.

        Example return value:
        [
          {
            "type": "NFS Share",
            "service": "nfs",
            "attachments": ["/mnt/tank/work"]
          }
        ]
        """
        return await attachments_impl(self.context, oid)

    @private
    async def attachments_with_path(
        self,
        path: str,
        check_parent: bool = False,
        exact_match: bool = False
    ) -> list[PoolAttachment]:
        """
        Query all registered attachment delegates to find services, shares, and tasks that depend on a given path.

        This method is the core of the attachment system, discovering what will be affected if a dataset at
        the specified path becomes unavailable (due to deletion, export, locking, etc.).

        Called by:
        - `pool.dataset.attachments()` - Public API method for querying dataset dependencies
        - `pool.info()` - When displaying pool-level attachment information
        - Internal pool operations - Before destructive operations to warn users or prevent conflicts

        Args:
            path (str): Filesystem path to check for attachments, typically a dataset mountpoint
                       (e.g., "/mnt/tank/work"). Method warns if path is not within /mnt/.
            check_parent (bool): If True, also match when path is a child of configured attachment paths.
                                This allows finding shares that consume the given path as a subdirectory.
                                Default: False (only match path as child of attachment paths).
            exact_match (bool): If True, only match when path exactly equals the attachment path.
                               Disables parent/child hierarchy matching.
                               Default: False (allow hierarchy matching).

        Returns:
            list[dict]: List of attachment groups, one per delegate type that has matches.
                       Each dict contains:
                       - type (str): Human-readable delegate title (e.g., "NFS Share", "SMB Share")
                       - service (str): Associated service name (e.g., "nfs", "cifs") or None
                       - attachments (list[str]): Human-readable names of matched attachments

        Example return value:
            [
                {
                    "type": "NFS Share",
                    "service": "nfs",
                    "attachments": ["/mnt/tank/work"]
                },
                {
                    "type": "Rsync Task",
                    "service": "rsync",
                    "attachments": ["Daily backup to /mnt/tank/work"]
                }
            ]
        """
        return await attachments_with_path(self.context, path, check_parent, exact_match)

    @private
    def register_attachment_delegate(self, delegate: FSAttachmentDelegate) -> None:
        """Register an attachment delegate for tracking dataset dependencies."""
        self.attachment_delegates.append(delegate)

    @private
    async def query_attachment_delegate(self, name: str, path: str, enabled: bool) -> list[dict]:
        """Query a specific attachment delegate by name for attachments at the given path."""
        for delegate in self.attachment_delegates:
            if delegate.name == name:
                return await delegate.query(path, enabled)
        raise RuntimeError(f'Unknown attachment delegate {name!r}')

    @private
    async def get_attachment_delegates(self) -> list[FSAttachmentDelegate]:
        """Get all registered attachment delegates."""
        return self.attachment_delegates

    @private
    async def get_attachment_delegates_for_start(self) -> list[FSAttachmentDelegate]:
        """
        Returns delegates sorted for start operations.
        Higher priority delegates (infrastructure) run first.
        """
        return await get_attachment_delegates_for_start(self.context)

    @private
    async def get_attachment_delegates_for_stop(self) -> list[FSAttachmentDelegate]:
        """
        Returns delegates sorted for stop operations.
        Lower priority delegates (dependent services) run first.
        """
        return await get_attachment_delegates_for_stop(self.context)

    @private
    async def stop_attachment_delegates(self, path: str | None) -> None:
        """
        Stop attachment delegates in priority order.
        Delegates with the same priority run in parallel, but different priority
        groups run sequentially (lower priority first).
        """
        return await stop_attachment_delegates_impl(self.context, path)

    @private
    @pass_thread_local_storage
    def query_for_quota_alert(self, tls: threading.local) -> dict[str, dict]:
        """
        Query quota information for alert system.

        Called exclusively by the alert system to inform users of quota thresholds.
        Returns information about pool and dataset quota usage.
        """
        return query_for_quota_alert(tls)

    @private
    @pass_thread_local_storage
    def get_quota_impl(self, tls: threading.local, ds: str, quota_type: str) -> list[dict]:
        """Get quota implementation with direct ZFS access."""
        return get_quota_impl(tls, ds, quota_type)

    @api_method(
        PoolDatasetGetQuotaArgs,
        PoolDatasetGetQuotaResult,
        roles=['DATASET_READ'],
        check_annotations=True,
    )
    async def get_quota(self, ds: str, quota_type: str, filters: QueryFilters, options: QueryOptions) -> list[dict] | dict | int:
        """
        Return a list of the specified `quota_type` of quotas on the ZFS dataset `ds`.
        Support `query-filters` and `query-options`.

        Note: SMB client requests to set a quota granting no space will result
        in an on-disk quota of 1 KiB.
        """
        return await get_quota(self.context, ds, quota_type, filters, options.model_dump())

    @private
    @pass_thread_local_storage
    def set_quota_impl(self, tls: threading.local, ds: str, inquotas: list[dict]) -> None:
        """Set quota implementation with direct ZFS access."""
        return set_quota_impl(tls, ds, inquotas)

    @api_method(
        PoolDatasetSetQuotaArgs,
        PoolDatasetSetQuotaResult,
        roles=['DATASET_WRITE'],
        check_annotations=True,
    )
    async def set_quota(self, ds: str, data: list[dict]) -> None:
        """
        Allow users to set multiple quotas simultaneously by submitting a list of quotas.

        Supports setting DATASET quotas (QUOTA/REFQUOTA) and USER/GROUP quotas.
        A quota_value of 0 removes the quota.
        """
        return await set_quota(self.context, ds, data)

    @api_method(
        PoolDatasetProcessesArgs,
        PoolDatasetProcessesResult,
        roles=['DATASET_READ'],
        check_annotations=True,
    )
    async def processes(self, oid: str) -> list[dict]:
        """
        Return a list of processes using this dataset.

        Example return value:

        [
          {
            "pid": 2520,
            "name": "smbd",
            "service": "cifs"
          },
          {
            "pid": 97778,
            "name": "minio",
            "cmdline": "/usr/local/bin/minio -C /usr/local/etc/minio server --address=0.0.0.0:9000 --quiet /mnt/tank/wk"
          }
        ]
        """
        return await processes_impl(self.context, oid)

    @private
    async def kill_processes(self, oid: str, control_services: bool, max_tries: int = 5) -> None:
        """
        Kill processes using a dataset.

        Attempts to stop services holding files open, or kills individual processes.
        Retries up to max_tries times before raising an error if processes won't stop.

        Args:
            oid: Dataset name
            control_services: If True, automatically stop/restart services holding the dataset
            max_tries: Maximum number of attempts to kill processes (default 5)

        Raises:
            CallError: If control_services is False and services need to be controlled,
                      or if processes cannot be stopped after max_tries attempts.
        """
        return await kill_processes(self.context, oid, control_services, max_tries)

    @private
    def processes_using_paths(
        self,
        paths: list[str],
        include_paths: bool = False,
        include_middleware: bool = False
    ) -> list[dict]:
        """
        Find processes using paths supplied via `paths`.

        Path may be an absolute path for a directory (e.g. /var/db/system) or a path
        in /dev/zvol or /dev/zd*

        Args:
            paths: List of paths to check for open files
            include_paths: Include paths that are open by the process in output.
                          By default this is not included for performance reasons.
            include_middleware: Include files opened by the middlewared process in output.
                               These are not included by default.

        Returns:
            List of processes with their details (pid, name, service, cmdline, optionally paths)
        """
        return processes_using_paths(self.context, paths, include_paths, include_middleware)

    @api_method(
        PoolDatasetLockArgs,
        PoolDatasetLockResult,
        roles=['DATASET_WRITE'],
        audit='Dataset lock',
        audit_extended=lambda data: data['id'],
        check_annotations=True,
    )
    @job(lock=lambda args: 'dataset_lock')
    async def lock(self, job: Job, id_: str, options: PoolDatasetLockOptions) -> Literal[True]:
        """
        Locks `id` dataset. It will unmount the dataset and its children before locking.

        After the dataset has been unmounted, system will set immutable flag on the dataset's mountpoint where
        the dataset was mounted before it was locked making sure that the path cannot be modified. Once the dataset
        is unlocked, it will not be affected by this change and consumers can continue consuming it.
        """
        return await lock_impl(self.context, job, id_, options)

    @api_method(
        PoolDatasetUnlockArgs,
        PoolDatasetUnlockResult,
        roles=['DATASET_WRITE'],
        audit='Dataset unlock',
        audit_extended=lambda data: data['id'],
        check_annotations=True,
    )
    @job(lock=lambda args: f'dataset_unlock_{args[0]}', pipes=['input'], check_pipes=False)
    def unlock(self, job: Job, id_: str, options: PoolDatasetUnlockOptions) -> dict:
        """
        Unlock dataset `id` (and its children if `unlock_options.recursive` is `true`).

        If `id` dataset is not encrypted an exception will be raised. There is one exception:
        when `id` is a root dataset and `unlock_options.recursive` is specified, encryption
        validation will not be performed for `id`. This allow unlocking encrypted children for the entire pool `id`.

        There are two ways to supply the key(s)/passphrase(s) for unlocking a dataset:

        1. Upload a json file which contains encrypted dataset keys (it will be read from the input pipe if
        `unlock_options.key_file` is `true`). The format is the one that is used for exporting encrypted dataset keys
        (`pool.export_keys`).

        2. Specify a key or a passphrase for each unlocked dataset using `unlock_options.datasets`.
        """
        return unlock_impl(self.context, job, id_, options)

    @private
    async def unlock_handle_attachments(self, dataset: dict) -> None:
        """
        Handle attachment delegates after unlocking a dataset.

        Starts attachment delegates for the unlocked dataset in priority order.
        Special handling for VM attachments.
        """
        return await unlock_handle_attachments(self.context, dataset)

    @api_method(
        PoolDatasetEncryptionSummaryArgs,
        PoolDatasetEncryptionSummaryResult,
        roles=['DATASET_READ'],
        check_annotations=True,
    )
    @job(lock=lambda args: f'encryption_summary_options_{args[0]}', pipes=['input'], check_pipes=False)
    def encryption_summary(self, job: Job, id_: str, options: PoolDatasetEncryptionSummaryOptions) -> list[PoolDatasetEncryptionSummary]:
        """
        Retrieve summary of all encrypted roots under `id`.

        Keys/passphrase can be supplied to check if the keys are valid.

        Example output:
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
            }
        ]
        """
        return encryption_summary_impl(self.context, job, id_, options)

    @periodic(86400)
    @private
    @job(lock=lambda args: f'sync_encrypted_pool_dataset_keys_{args}')
    def sync_db_keys(self, job: Job, name: str | None = None) -> None:
        """
        Sync database encryption keys with actual ZFS dataset keys.

        Called periodically to ensure database keys are valid and remove stale entries.
        Only runs on single/master nodes (not passive controller).
        """
        return sync_db_keys_impl(self.context, job, name)

    @private
    @pass_thread_local_storage
    def path_in_locked_datasets(self, tls: threading.local, path: str) -> bool:
        """
        Check whether the path or any parent components of said path are locked.

        WARNING: EXTREMELY hot code path. Do not add more things here unless
        you fully understand the side-effects.

        Parameters:
            path (str): The filesystem path to be checked.

        Returns:
            bool: True if the path or any parent component of the path is locked, False otherwise.

        Raises:
            ZFSException/Exception: If an unexpected error occurs
        """
        return path_in_locked_datasets(tls, path)

    @private
    def query_encrypted_roots_keys(self, filters: list) -> dict[str, str]:
        """
        Query encryption keys from database and KMIP for encrypted datasets.

        Returns a dict mapping dataset names to their encryption keys.
        """
        return query_encrypted_roots_keys(self.context, filters)

    @private
    def query_encrypted_datasets(self, name: str, options: dict | None = None) -> dict[str, dict]:
        """
        Common function to retrieve encrypted datasets and their keys.

        Args:
            name: Dataset name to query
            options: Optional dict with 'key_loaded' (default True) and 'all' flags

        Returns:
            Dict mapping dataset names to dataset info including encryption_key
        """
        return query_encrypted_datasets(self.context, name, options)

    @api_method(
        PoolDatasetExportKeysArgs,
        PoolDatasetExportKeysResult,
        roles=['DATASET_WRITE', 'REPLICATION_TASK_WRITE'],
        check_annotations=True,
    )
    @job(lock='dataset_export_keys', pipes=['output'])
    def export_keys(self, job: Job, id_: str) -> None:
        """
        Export keys for `id` and its children which are stored in the system.

        The exported file is a JSON file which has a dictionary containing dataset
        names as keys and their keys as the value.

        Please refer to websocket documentation for downloading the file.
        """
        return export_keys_impl(self.context, job, id_)

    @api_method(
        PoolDatasetExportKeysForReplicationArgs,
        PoolDatasetExportKeysForReplicationResult,
        roles=['DATASET_WRITE', 'REPLICATION_TASK_WRITE'],
        check_annotations=True,
    )
    @job(pipes=['output'])
    def export_keys_for_replication(self, job: Job, task_id: int) -> None:
        """
        Export keys for replication task `id` for source dataset(s) which are stored in the system.

        The exported file is a JSON file which has a dictionary containing dataset names
        as keys and their keys as the value.

        Please refer to websocket documentation for downloading the file.
        """
        return export_keys_for_replication_impl(self.context, job, task_id)

    @private
    async def export_keys_for_replication_internal(
        self,
        replication_task_or_id: int | dict,
        dataset_encryption_root_mapping: dict | None = None,
        skip_syncing_db_keys: bool = False,
    ) -> dict[str, str]:
        """
        Internal helper for exporting keys for replication tasks.

        Handles mapping source dataset encryption keys to their destination paths
        based on replication task configuration.
        """
        return await export_keys_for_replication_internal(
            self.context, replication_task_or_id, dataset_encryption_root_mapping, skip_syncing_db_keys
        )

    @private
    async def dataset_encryption_root_mapping(self) -> dict[str, list[dict]]:
        """
        Build mapping of encryption roots to their child datasets.

        Returns dict where keys are encryption root names and values are lists
        of all datasets using that encryption root.
        """
        return await dataset_encryption_root_mapping_impl(self.context)

    @api_method(
        PoolDatasetExportKeyArgs,
        PoolDatasetExportKeyResult,
        roles=['DATASET_WRITE'],
        check_annotations=True,
    )
    @job(lock='dataset_export_keys', pipes=['output'], check_pipes=False)
    def export_key(self, job: Job, id_: str, download: bool) -> str | None:
        """
        Export own encryption key for dataset `id`.

        If `download` is `true`, key will be downloaded in a json file where the same
        file can be used to unlock the dataset, otherwise it will be returned as string.

        Please refer to websocket documentation for downloading the file.
        """
        return export_key_impl(self.context, job, id_, download)

    @private
    @api_method(
        PoolDatasetInsertOrUpdateEncryptedRecordArgs,
        PoolDatasetInsertOrUpdateEncryptedRecordResult,
        roles=['DATASET_WRITE'],
        check_annotations=True,
    )
    async def insert_or_update_encrypted_record(self, data: PoolDatasetInsertOrUpdateEncryptedRecordData) -> int | None:
        """
        Insert or update encrypted dataset record in database.

        Stores encryption key information for datasets encrypted with keys (not passphrases).
        Integrates with KMIP for key management when enabled.
        """
        return await insert_or_update_encrypted_record(self.context, data)

    @private
    async def delete_encrypted_datasets_from_db(self, filters: list) -> None:
        """
        Delete encrypted dataset records from database matching the given filters.

        Also cleans up KMIP keys if KMIP integration is enabled.
        """
        return await delete_encrypted_datasets_from_db(self.context, filters)

    @private
    def validate_encryption_data(self, job: Job | None, verrors: ValidationErrors, encryption_dict: dict, schema: str) -> dict:
        """
        Validate encryption configuration and prepare encryption options.

        Validates key/passphrase options, generates keys if requested, and prepares
        encryption properties dict for ZFS operations.

        Args:
            job: Optional job for reading key from input pipe
            verrors: ValidationErrors object to collect validation errors
            encryption_dict: Dict with encryption configuration
            schema: Schema name for error messages

        Returns:
            Dict with ZFS encryption properties or empty dict if validation fails
        """
        return validate_encryption_data(self.context, job, verrors, encryption_dict, schema)

    @api_method(
        PoolDatasetChangeKeyArgs,
        PoolDatasetChangeKeyResult,
        roles=['DATASET_WRITE'],
        check_annotations=True,
    )
    @job(lock=lambda args: f'dataset_change_key_{args[0]}', pipes=['input'], check_pipes=False)
    async def change_key(self, job: Job, id_: str, options: PoolDatasetChangeKeyOptions) -> None:
        """
        Change encryption properties for `id` encrypted dataset.

        Changing dataset encryption to use passphrase instead of a key is not allowed if:

        1) It has encrypted roots as children which are encrypted with a key
        2) If it is a root dataset where the system dataset is located
        """
        return await change_key_impl(self.context, job, id_, options)

    @api_method(
        PoolDatasetInheritParentEncryptionPropertiesArgs,
        PoolDatasetInheritParentEncryptionPropertiesResult,
        roles=['DATASET_WRITE'],
        check_annotations=True,
    )
    async def inherit_parent_encryption_properties(self, id_: str) -> None:
        """
        Allows inheriting parent's encryption root discarding its current encryption settings.

        This can only be done where `id` has an encrypted parent and `id` itself is an
        encryption root.
        """
        return await inherit_parent_encryption_properties_impl(self.context, id_)

    @api_method(
        PoolDatasetChecksumChoicesArgs,
        PoolDatasetChecksumChoicesResult,
        roles=['DATASET_READ'],
        check_annotations=True,
    )
    async def checksum_choices(self) -> PoolDatasetChecksumChoices:
        """
        Retrieve checksums supported for ZFS dataset.
        """
        return PoolDatasetChecksumChoices()

    @api_method(
        PoolDatasetCompressionChoicesArgs,
        PoolDatasetCompressionChoicesResult,
        roles=['DATASET_READ'],
        check_annotations=True,
    )
    async def compression_choices(self) -> dict[str, str]:
        """
        Retrieve compression algorithm supported by ZFS.
        """
        return {v: v for v in ZFS_COMPRESSION_ALGORITHM_CHOICES}

    @api_method(
        PoolDatasetEncryptionAlgorithmChoicesArgs,
        PoolDatasetEncryptionAlgorithmChoicesResult,
        roles=['DATASET_READ'],
        check_annotations=True,
    )
    async def encryption_algorithm_choices(self) -> PoolDatasetEncryptionAlgorithmChoices:
        """
        Retrieve encryption algorithms supported for ZFS dataset encryption.
        """
        return PoolDatasetEncryptionAlgorithmChoices()

    @api_method(
        PoolDatasetRecommendedZvolBlocksizeArgs,
        PoolDatasetRecommendedZvolBlocksizeResult,
        roles=['DATASET_READ'],
        check_annotations=True,
    )
    async def recommended_zvol_blocksize(self, pool: str) -> str:
        """
        Helper method to get recommended size for a new zvol (dataset of type VOLUME).

        .. examples(websocket)::

          Get blocksize for pool "tank".

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.dataset.recommended_zvol_blocksize",
                "params": ["tank"]
            }
        """
        return await recommended_zvol_blocksize_impl(self.context, pool)

    @api_method(
        PoolDatasetRecordsizeChoicesArgs,
        PoolDatasetRecordsizeChoicesResult,
        roles=['DATASET_READ'],
        check_annotations=True,
    )
    def recordsize_choices(self, pool_name: str | None) -> list[str]:
        """
        Retrieve recordsize choices for datasets.

        Returns available recordsize values based on system ZFS configuration and pool type.
        dRAID pools have a minimum recordsize of 128K.
        """
        return recordsize_choices_impl(self.context, pool_name)
