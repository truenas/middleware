import errno
import os
import pathlib
from typing import Iterable, Literal

from truenas_pylibzfs import ZFSError, ZFSException, ZFSType

from middlewared.api.current import (
    PoolDatasetEntry,
    PoolDatasetCreateFilesystem, PoolDatasetCreateVolume,
    ZFSResourceQuery,
)
from middlewared.plugins.container.utils import CONTAINER_DS_NAME
from middlewared.plugins.zfs_.validation_utils import validate_dataset_name
from middlewared.plugins.zfs.utils import has_internal_path
from middlewared.service import (
    CallError, InstanceNotFound, ServiceContext, ValidationError, ValidationErrors,
)
import middlewared.sqlalchemy as sa
from middlewared.utils import BOOT_POOL_NAME_VALID
from middlewared.utils.filter_list import filter_list

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
    ZFS_VOLUME_BLOCK_SIZE_CHOICES
)


class PoolDatasetEncryptionModel(sa.Model):
    __tablename__ = 'storage_encrypteddataset'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(255))
    encryption_key = sa.Column(sa.EncryptedText(), nullable=True)
    kmip_uid = sa.Column(sa.String(255), nullable=True, default=None)


class Config:
    cli_namespace = 'storage.dataset'
    datastore_primary_key_type = 'string'
    event_send = False
    namespace = 'pool.dataset'
    role_prefix = 'DATASET'
    role_separate_delete = True
    entry = PoolDatasetEntry


async def get_instance_quick(
    ctx: ServiceContext, name: str,
    properties: Iterable[str] | None = None, encryption: bool = False, retrieve_children: bool = False
) -> PoolDatasetEntry:
    properties = set(properties or [])
    properties.add('mountpoint')
    if encryption:
        properties.update(['encryption', 'keystatus', 'mountpoint', 'keyformat', 'encryptionroot'])

    return await ctx.call2(
        ctx.s.pool.dataset.get_instance, name, {
            'extra': {
                'retrieve_children': retrieve_children,
                'properties': list(properties),
            }
        }
    )


async def common_validation(
    ctx: ServiceContext, verrors: ValidationErrors, schema: str, data, mode: Literal['CREATE', 'UPDATE'],
    parent=None, cur_dataset=None
) -> None:
    assert mode in ('CREATE', 'UPDATE')

    parents = get_dataset_parents(data['name'])
    parent_name = None
    if not parents:
        # happens when someone is making
        # changes to the root dataset (zpool)
        parent_name = data['name']
    else:
        parent_name = parents[0]

    if not parent:
        parent = await ctx.call2(
            ctx.s.pool.dataset.query,
            [('id', '=', parent_name)],
            {'extra': {'retrieve_children': False}}
        )

    if await ctx.is_internal_dataset(data['name']):
        verrors.add(
            f'{schema}.name',
            f'{data["name"]!r} is using system internal managed dataset. Please specify a different parent.'
        )

    if not parent:
        # This will only be true on dataset creation
        if data['create_ancestors']:
            verrors.add(
                f'{schema}.name',
                'Please specify a pool which exists for the dataset/volume to be created'
            )
        else:
            msg = f'({parent_name}) does not exist.'
            if len(parents) == 1:
                msg = f'zpool {msg}'
            else:
                msg = f'Parent dataset {msg}'
            verrors.add(f'{schema}.name', msg)
    else:
        parent = parent[0]
        if mode == 'CREATE' and parent['readonly']['rawvalue'] == 'on':
            # creating a zvol/dataset when the parent object is set to readonly=on
            # is allowed via ZFS. However, if it's a dataset an error will be raised
            # stating that it was unable to be mounted. If it's a zvol, then the service
            # that tries to open the zvol device will get read only related errors.
            # Currently, there is no way to mount a dataset in the webUI so we will
            # prevent this scenario from occuring by preventing creation if the parent
            # is set to readonly=on.
            verrors.add(
                f'{schema}.readonly',
                f'Turn off readonly mode on {parent["id"]} to create {data["name"].rsplit("/")[0]}'
            )

    # We raise validation errors here as parent could be used down to validate other aspects of the dataset
    verrors.check()

    dataset_pool_is_draid = await ctx.middleware.call('pool.is_draid_pool', parent['pool'])
    if data['type'] == 'FILESYSTEM':
        to_check = {'acltype': None, 'aclmode': None}

        if mode == 'UPDATE':
            # Prevent users from changing acltype settings underneath an active SMB share
            # If this dataset hosts an SMB share, then prompt the user to first delete the share,
            # make the dataset change, the recreate the share.
            acltype = data.get('acltype')
            if acltype == 'INHERIT':
                acltype = parent['acltype']['value']

            if acltype and acltype != cur_dataset['acltype']['value']:
                ds_attachments = await ctx.call2(ctx.s.pool.dataset.attachments, data['name'])
                if smb_attachments := [share for share in ds_attachments if share.type == "SMB Share"]:
                    share_names = [smb_share.attachments for smb_share in smb_attachments]

                    verrors.add(
                        f'{schema}.acltype',
                        'This dataset is hosting SMB shares. '
                        f'Before acltype can be updated the following shares must be disabled: '
                        f'{share_names[0]}. '
                        'The shares may be re-enabled after the change.'
                    )

        # Prevent users from setting incorrect combinations of aclmode and acltype parameters
        # The final value to be set may have one of several different possible origins
        # 1. The parameter may be provided in `data` (explicit creation or update)
        # 2. The parameter may be original value stored in dataset and not touched by update payload
        # 3. The parameter may be omitted from payload (data) in creation (defaulted to INHERIT)
        #
        # If result of 1-3 above for aclmode is INHERIT, then value will be retrieved from parent
        #
        # The configuration options we want to avoid are:
        # NFSV4 + DISCARD (this will result in ACL being stripped on chmod operation)
        #
        # POSIX / OFF + non-DISCARD (this will potentially prevent ZFS_ACL_TRIVAL ZFS pflag from being
        # set and may result in spurious permissions errors.
        for key in ('acltype', 'aclmode'):
            match (val := data.get(key) or (cur_dataset[key]['value'] if cur_dataset else 'INHERIT')):
                case 'INHERIT':
                    to_check[key] = parent[key]['value']
                case 'NFSV4' | 'POSIX' | 'OFF' | 'PASSTHROUGH' | 'RESTRICTED' | 'DISCARD':
                    to_check[key] = val
                case _:
                    raise CallError(f'{val}: unexpected value for {key}')

        if to_check['acltype'] in ('POSIX', 'OFF') and to_check['aclmode'] != 'DISCARD':
            verrors.add(f'{schema}.aclmode', 'Must be set to DISCARD when acltype is POSIX or OFF')

        elif to_check['acltype'] == 'NFSV4' and to_check['aclmode'] == 'DISCARD':
            verrors.add(f'{schema}.aclmode', 'DISCARD aclmode may not be set for NFSv4 acl type')

        for i in ('force_size', 'sparse', 'volsize', 'volblocksize'):
            if i in data:
                verrors.add(f'{schema}.{i}', 'This field is not valid for FILESYSTEM')

        if rs := data.get('recordsize'):
            if rs != 'INHERIT' and rs not in await ctx.middleware.call(
                'pool.dataset.recordsize_choices', parent['pool']
            ):
                verrors.add(f'{schema}.recordsize', f'{rs!r} is an invalid recordsize.')
        elif mode == 'CREATE' and dataset_pool_is_draid:
            # We set recordsize to 1M by default on dataset creation if not explicitly specified
            data['recordsize'] = '1M'

    elif data['type'] == 'VOLUME':
        if mode == 'CREATE' and 'volblocksize' not in data:
            # with openzfs 2.2, zfs sets 16k as default https://github.com/openzfs/zfs/pull/12406
            data['volblocksize'] = '128K' if dataset_pool_is_draid else '16K'

        if dataset_pool_is_draid and 'volblocksize' in data:
            if ZFS_VOLUME_BLOCK_SIZE_CHOICES[data['volblocksize']] < 32 * 1024:
                verrors.add(
                    f'{schema}.volblocksize',
                    'Volume block size must be greater than or equal to 32K for dRAID pools'
                )

        for i in (
            'aclmode', 'acltype', 'atime', 'casesensitivity', 'quota', 'refquota', 'recordsize',
        ):
            if i in data:
                verrors.add(f'{schema}.{i}', 'This field is not valid for VOLUME')

        if 'volsize' in data and parent:

            avail_mem = int(parent['available']['rawvalue'])

            if mode == 'UPDATE':
                avail_mem += int((await ctx.get_instance(data['name']))['used']['rawvalue'])

            if (
                data['volsize'] > (avail_mem * 0.80) and
                not data.get('force_size', False)
            ):
                verrors.add(
                    f'{schema}.volsize',
                    'It is not recommended to use more than 80% of your available space for VOLUME'
                )

            if 'volblocksize' in data:

                if data['volblocksize'][:3] == '512':
                    block_size = 512
                else:
                    block_size = int(data['volblocksize'][:-1]) * 1024

                if data['volsize'] % block_size:
                    verrors.add(
                        f'{schema}.volsize',
                        'Volume size should be a multiple of volume block size'
                    )

    if (c_value := data.get('special_small_block_size')) is not None:
        if c_value != 'INHERIT' and not (0 <= c_value <= 16 * 1048576):
            verrors.add(
                f'{schema}.special_small_block_size',
                'This field must be from zero to 16M'
            )

    if mode == 'UPDATE':
        if data.get('user_properties_update') and not data.get('user_properties'):
            for index, prop in enumerate(data['user_properties_update']):
                prop_schema = f'{schema}.user_properties_update.{index}'
                if 'value' in prop and prop.get('remove'):
                    verrors.add(f'{prop_schema}.remove', 'When "value" is specified, this cannot be set')
                elif not any(k in prop for k in ('value', 'remove')):
                    verrors.add(f'{prop_schema}.value', 'Either "value" or "remove" must be specified')
        elif data.get('user_properties') and data.get('user_properties_update'):
            verrors.add(
                f'{schema}.user_properties_update',
                'Should not be specified when "user_properties" are explicitly specified'
            )
        elif data.get('user_properties'):
            # Let's normalize this so that we create/update/remove user props accordingly
            user_props = {p['key'] for p in data['user_properties']}
            data['user_properties_update'] = data['user_properties']
            for prop_key in [k for k in cur_dataset['user_properties'] if k not in user_props]:
                data['user_properties_update'].append({
                    'key': prop_key,
                    'remove': True,
                })


def create_impl(self, tls, data: CreateImplArgs):
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


async def do_create(ctx, data: PoolDatasetCreateFilesystem | PoolDatasetCreateVolume) -> PoolDatasetEntry:
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
            while not await ctx.middleware.call(
                'pool.dataset.query',
                [['id', '=', parent_name]], {
                    'extra': {'retrieve_children': False, 'properties': []}
                }
            ):
                if '/' not in parent_name:
                    # Root dataset / pool does not exist
                    break
                parent_name = parent_name.rsplit('/', 1)[0]

        parent_ds = await ctx.middleware.call(
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

        await common_validation(ctx, verrors, 'pool_dataset_create', data, 'CREATE', parent_ds)

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
        parent_st = await ctx.middleware.call('filesystem.stat', parent_mp)
        parent_st['acltype'] = await ctx.middleware.call('filesystem.path_get_acltype', parent_mp)

    mountpoint = os.path.join('/mnt', data.name)

    try:
        await ctx.middleware.call('filesystem.stat', mountpoint)
        verrors.add('pool_dataset_create.name', f'Path {mountpoint} already exists')
    except CallError as e:
        if e.errno != errno.ENOENT:
            raise

    if data.type == 'FILESYSTEM':
        if data.share_type == 'SMB':
            if parent_st['acl'] and parent_st['acltype'] == 'NFS4':
                acl_to_set = await ctx.middleware.call('filesystem.get_inherited_acl', {
                    'path': os.path.join('/mnt', parent_name),
                })
            else:
                acl_to_set = (await ctx.middleware.call('filesystem.acltemplate.by_path', {
                    'query-filters': [('name', '=', 'NFS4_RESTRICTED')],
                    'format-options': {'canonicalize': True, 'ensure_builtins': True},
                }))[0]['acl']
        elif data.share_type == 'APPS':
            must_add_apps = True
            if parent_st['acl'] and parent_st['acltype'] == 'NFS4':
                acl_to_set = await ctx.middleware.call('filesystem.get_inherited_acl', {
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
                acl_to_set = (await ctx.middleware.call('filesystem.acltemplate.by_path', {
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
                acl_to_set = await ctx.middleware.call('filesystem.get_inherited_acl', {
                    'path': os.path.join('/mnt', parent_name),
                })

    if acl_to_set:
        try:
            await ctx.middleware.call(
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
            check_ds = await ctx.middleware.call('pool.dataset.get_instance_quick', parent, {'encryption': True})
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
                    (await ctx.get_instance(parent_encryption_root))['key_format']['value']
                ) == ZFSKeyFormat.PASSPHRASE
            ):
                verrors.add(
                    'pool_dataset_create.encryption',
                    'Passphrase encrypted datasets cannot have children encrypted with a key.'
                )

    encryption_dict = await ctx.middleware.call(
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

    await ctx.middleware.call(
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
    await ctx.middleware.call('pool.dataset.insert_or_update_encrypted_record', dataset_data)
    await ctx.middleware.call_hook('dataset.post_create', {'encrypted': bool(encryption_dict), **dataset_data})

    created_ds = await ctx.get_instance(data.name)

    if acl_to_set:
        # We're potentially auto-inheriting an ACL containing nested
        # security groups and so we need to skip the ACL validation
        acl_job = await ctx.middleware.call('filesystem.setacl', {
            'path': mountpoint,
            'dacl': acl_to_set,
            'options': {'validate_effective_acl': False}
        })
        await acl_job.wait(raise_error=True)

    ctx.middleware.send_event('pool.dataset.query', 'ADDED', id=data.name, fields=created_ds)
    return created_ds


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


async def update(self, audit_callback, id_, data):
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
    verrors = ValidationErrors()

    dataset = await self.middleware.call(
        'pool.dataset.query', [('id', '=', id_)], {'extra': {'retrieve_children': False}}
    )
    if dataset:
        data['type'] = dataset[0]['type']
        data['name'] = dataset[0]['name']
        audit_callback(data['name'])
        if data['type'] == 'VOLUME':
            data['volblocksize'] = dataset[0]['volblocksize']['value']
        await common_validation(ctx, verrors, 'pool_dataset_update', data, 'UPDATE', cur_dataset=dataset[0])
        if 'volsize' in data:
            if data['volsize'] < dataset[0]['volsize']['parsed']:
                verrors.add('pool_dataset_update.volsize',
                            'You cannot shrink a zvol from GUI, this may lead to data loss.')
        if dataset[0]['type'] == 'VOLUME':
            existing_snapdev_prop = dataset[0]['snapdev']['parsed'].upper()
            snapdev_prop = data.get('snapdev') or existing_snapdev_prop
            if existing_snapdev_prop != snapdev_prop and snapdev_prop in ('INHERIT', 'HIDDEN'):
                if await self.call2(
                    self.s.zfs.resource.unlocked_zvols_fast,
                    [['attachment', '!=', None], ['ro', '=', True], ['name', '^', f'{id_}@']],
                    {},
                    ['RO', 'ATTACHMENT']
                ):
                    verrors.add(
                        'pool_dataset_update.snapdev',
                        f'{id_!r} has snapshots which have attachments being used. Before marking it '
                        'as HIDDEN, remove attachment usages.'
                    )
    else:
        verrors.add('id', f'{id_} does not exist', errno.ENOENT)

    verrors.check()

    uia: UpdateImplArgs = UpdateImplArgs(name=id_)
    # Since TypedDict doesn't provide defaults, we need to ensure these exist
    if 'zprops' not in uia:
        uia['zprops'] = {}
    if 'uprops' not in uia:
        uia['uprops'] = {}
    if 'iprops' not in uia:
        uia['iprops'] = set()

    for prop in POOL_DS_UPDATE_PROPERTIES:
        if prop.api_name not in data:
            continue
        if prop.inheritable and data[prop.api_name] == 'INHERIT':
            uia['iprops'].add(prop.real_name)
            if prop.real_name == 'acltype':
                uia['iprops'].add('aclmode')
                uia['iprops'].add('aclinherit')
        else:
            if not prop.transform:
                transformed = data[prop.api_name]
            else:
                transformed = prop.transform(data[prop.api_name])

            if prop.is_user_prop:
                uia['uprops'][prop.real_name] = transformed
            else:
                uia['zprops'][prop.real_name] = transformed

            if prop.real_name == 'acltype':
                if uia['zprops'][prop.real_name] == 'nfsv4':
                    uia['zprops'].update({'aclinherit': 'passthrough'})
                elif uia['zprops'][prop.real_name] in ('posix', 'off'):
                    uia['zprops'].update({'aclmode': 'discard', 'aclinherit': 'discard'})

    for up in data.get('user_properties_update', []):
        if 'value' in up:
            uia['uprops'][up['key']] = up['value']
        elif up.get('remove'):
            uia['iprops'].add(up['key'])

    try:
        await self.middleware.call('pool.dataset.update_impl', uia)
    except ZFSException as e:
        raise ValidationError("pool.dataset.update", f"Failed to update properties: {e}")
    except Exception as e:
        raise CallError(f'Failed to update dataset properties: {e}')

    if data['type'] == 'VOLUME':
        if 'volsize' in data and data['volsize'] > dataset[0]['volsize']['parsed']:
            # means the zvol size has increased so we need to check if this zvol is shared via SCST (iscsi)
            # and if it is, resync it so the connected initiators can see the new size of the zvol
            await self.middleware.call('iscsi.global.resync_lun_size_for_zvol', id_)
            await self.middleware.call('nvmet.namespace.resync_lun_size_for_zvol', id_)

        if 'readonly' in data:
            # depending on the iscsi client connected to us, if someone marks a zvol
            # as R/O (or R/W), we need to be sure and update the associated extent so
            # that we don't get into a scenario where the iscsi extent is R/W but the
            # underlying zvol is R/O. Windows clients seem to not handle this very well.
            await self.middleware.call('iscsi.global.resync_readonly_property_for_zvol', id_, data['readonly'])

    updated_ds = await self.get_instance(id_)
    self.middleware.send_event('pool.dataset.query', 'CHANGED', id=id_, fields=updated_ds)
    return updated_ds


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


async def promote(self, id_):
    """Promote a cloned dataset."""
    return await self.call2(self.s.zfs.resource.promote, id_)


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
