import copy
import errno
import os

from middlewared.api import api_method
from middlewared.api.current import (
    PoolDatasetEntry, PoolDatasetCreateArgs, PoolDatasetCreateResult, PoolDatasetUpdateArgs, PoolDatasetUpdateResult,
    PoolDatasetDeleteArgs, PoolDatasetDeleteResult, PoolDatasetDestroySnapshotsArgs, PoolDatasetDestroySnapshotsResult,
    PoolDatasetPromoteArgs, PoolDatasetPromoteResult, PoolDatasetRenameArgs, PoolDatasetRenameResult,
)
from middlewared.plugins.zfs_.exceptions import ZFSSetPropertyError
from middlewared.plugins.zfs_.validation_utils import validate_dataset_name
from middlewared.service import (
    CallError, CRUDService, InstanceNotFound, item_method, job, private, ValidationError, ValidationErrors,
    filterable_api_method,
)
import middlewared.sqlalchemy as sa
from middlewared.utils import filter_list, BOOT_POOL_NAME_VALID

from .utils import (
    dataset_mountpoint, get_dataset_parents, get_props_of_interest_mapping, none_normalize, ZFSKeyFormat,
    ZFS_VOLUME_BLOCK_SIZE_CHOICES, TNUserProp
)


class PoolDatasetEncryptionModel(sa.Model):
    __tablename__ = 'storage_encrypteddataset'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(255))
    encryption_key = sa.Column(sa.EncryptedText(), nullable=True)
    kmip_uid = sa.Column(sa.String(255), nullable=True, default=None)


class PoolDatasetService(CRUDService):

    class Config:
        cli_namespace = 'storage.dataset'
        datastore_primary_key_type = 'string'
        event_send = False
        namespace = 'pool.dataset'
        role_prefix = 'DATASET'
        role_separate_delete = True
        entry = PoolDatasetEntry

    @private
    async def get_instance_quick(self, name, options=None):
        options = options or {}
        properties = set(options.get('properties') or [])
        properties.add('mountpoint')
        if options.get('encryption'):
            properties.update(['encryption', 'keystatus', 'mountpoint', 'keyformat', 'encryptionroot'])

        return await self.middleware.call(
            'pool.dataset.get_instance', name, {
                'extra': {
                    'retrieve_children': options.get('retrieve_children', False),
                    'properties': list(properties),
                }
            }
        )

    def _internal_user_props(self):
        return TNUserProp.values()

    def __transform(self, datasets, retrieve_children, children_filters, retrieve_user_props):
        """
        We need to transform the data zfs gives us to make it consistent/user-friendly,
        making it match whatever pool.dataset.{create,update} uses as input.
        """

        def transform(dataset):
            for orig_name, new_name, method in get_props_of_interest_mapping():
                if orig_name not in dataset['properties']:
                    continue
                i = new_name or orig_name
                dataset[i] = dataset['properties'][orig_name]
                if method:
                    dataset[i]['value'] = method(dataset[i]['value'])

            if 'mountpoint' in dataset:
                # This is treated specially to keep backwards compatibility with API
                dataset['mountpoint'] = dataset['mountpoint']['value']
            if dataset['type'] == 'VOLUME':
                dataset['mountpoint'] = None

            if retrieve_user_props:
                dataset['user_properties'] = {
                    k: v for k, v in dataset['properties'].items() if ':' in k and k not in self._internal_user_props()
                }
            del dataset['properties']

            if all(k in dataset for k in ('encrypted', 'key_loaded')):
                dataset['locked'] = dataset['encrypted'] and not dataset['key_loaded']

            if retrieve_children:
                rv = []
                for child in filter_list(dataset['children'], children_filters):
                    rv.append(transform(child))
                dataset['children'] = rv

            return dataset

        rv = []
        for dataset in datasets:
            rv.append(transform(dataset))
        return rv

    @private
    async def internal_datasets_filters(self):
        # We get filters here which ensure that we don't match an internal dataset
        return [
            ['pool', 'nin', BOOT_POOL_NAME_VALID],
            ['id', 'rnin', '/.system'],
            ['id', 'rnin', '/ix-applications/'],
            ['id', 'rnin', '/ix-apps'],
            ['id', 'rnin', '/.ix-virt'],
        ]

    @private
    async def is_internal_dataset(self, dataset):
        pool = dataset.split('/')[0]
        return not bool(filter_list([{'id': dataset, 'pool': pool}], await self.internal_datasets_filters()))

    @filterable_api_method(item=PoolDatasetEntry)
    def query(self, filters, options):
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
        # Optimization for cases in which they can be filtered at zfs.dataset.query
        zfsfilters = []
        filters = filters or []
        if len(filters) == 1 and len(f := filters[0]) == 3 and f[0] in ('id', 'name') and f[1] in ('=', 'in'):
            zfsfilters.append(copy.deepcopy(f))

        internal_datasets_filters = self.middleware.call_sync('pool.dataset.internal_datasets_filters')
        filters.extend(internal_datasets_filters)
        extra = copy.deepcopy(options.get('extra', {}))
        retrieve_children = extra.get('retrieve_children', True)
        props = extra.get('properties')
        snapshots = extra.get('snapshots')
        snapshots_recursive = extra.get('snapshots_recursive')
        snapshots_count = extra.get('snapshots_count')
        retrieve_user_props = extra.get('retrieve_user_props', True)
        return filter_list(
            self.__transform(self.middleware.call_sync(
                'zfs.dataset.query', zfsfilters, {
                    'extra': {
                        'flat': extra.get('flat', True),
                        'retrieve_children': retrieve_children,
                        'properties': props,
                        'snapshots': snapshots,
                        'snapshots_recursive': snapshots_recursive,
                        'snapshots_count': snapshots_count,
                        'snapshots_properties': extra.get('snapshots_properties', []),
                        'user_properties': retrieve_user_props,
                    }
                }
            ), retrieve_children, internal_datasets_filters, retrieve_user_props,
            ), filters, options
        )

    @private
    async def get_create_update_user_props(self, user_properties, update=False):
        props = {}
        for prop in user_properties:
            if 'value' in prop:
                props[prop['key']] = {'value': prop['value']} if update else prop['value']
            elif prop.get('remove'):
                props[prop['key']] = {'source': 'INHERIT'}
        return props

    async def __common_validation(self, verrors, schema, data, mode, parent=None, cur_dataset=None):
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
            parent = await self.middleware.call(
                'pool.dataset.query',
                [('id', '=', parent_name)],
                {'extra': {'retrieve_children': False}}
            )

        if await self.is_internal_dataset(data['name']):
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

        dataset_pool_is_draid = await self.middleware.call('pool.is_draid_pool', parent['pool'])
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
                    ds_attachments = await self.middleware.call('pool.dataset.attachments', data['name'])
                    if smb_attachments := [share for share in ds_attachments if share['type'] == "SMB Share"]:
                        share_names = [smb_share['attachments'] for smb_share in smb_attachments]

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

            if (c_value := data.get('special_small_block_size')) is not None:
                if c_value != 'INHERIT' and not (
                    (c_value == 0 or 512 <= c_value <= 1048576) and ((c_value & (c_value - 1)) == 0)
                ):
                    verrors.add(
                        f'{schema}.special_small_block_size',
                        'This field must be zero or a power of 2 from 512B to 1M'
                    )

            if rs := data.get('recordsize'):
                if rs != 'INHERIT' and rs not in await self.middleware.call(
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
                    avail_mem += int((await self.get_instance(data['name']))['used']['rawvalue'])

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

    @api_method(
        PoolDatasetCreateArgs,
        PoolDatasetCreateResult,
        audit='Pool dataset create',
        audit_extended=lambda data: data['name']
    )
    async def do_create(self, data):
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

        if '/' not in data['name']:
            verrors.add('pool_dataset_create.name', 'You need a full name, e.g. pool/newdataset')
        elif not validate_dataset_name(data['name']):
            verrors.add('pool_dataset_create.name', 'Invalid dataset name')
        elif data['name'][-1] == ' ':
            verrors.add(
                'pool_dataset_create.name',
                'Trailing spaces are not permitted in dataset names'
            )
        else:
            parent_name = data['name'].rsplit('/', 1)[0]
            if data['create_ancestors']:
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

            match data['share_type']:
                case 'SMB':
                    data['casesensitivity'] = 'INSENSITIVE'
                    data['acltype'] = 'NFSV4'
                    data['aclmode'] = 'RESTRICTED'
                case 'APPS' | 'MULTIPROTOCOL' | 'NFS':
                    data['casesensitivity'] = 'SENSITIVE'
                    data['atime'] = 'OFF'
                    data['acltype'] = 'NFSV4'
                    data['aclmode'] = 'PASSTHROUGH'

            await self.__common_validation(verrors, 'pool_dataset_create', data, 'CREATE', parent_ds)

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

        mountpoint = os.path.join('/mnt', data['name'])

        try:
            await self.middleware.call('filesystem.stat', mountpoint)
            verrors.add('pool_dataset_create.name', f'Path {mountpoint} already exists')
        except CallError as e:
            if e.errno != errno.ENOENT:
                raise

        if data['share_type'] == 'SMB':
            if parent_st['acl'] and parent_st['acltype'] == 'NFS4':
                acl_to_set = await self.middleware.call('filesystem.get_inherited_acl', {
                    'path': os.path.join('/mnt', parent_name),
                })
            else:
                acl_to_set = (await self.middleware.call('filesystem.acltemplate.by_path', {
                    'query-filters': [('name', '=', 'NFS4_RESTRICTED')],
                    'format-options': {'canonicalize': True, 'ensure_builtins': True},
                }))[0]['acl']
        elif data['share_type'] == 'APPS':
            if parent_st['acl'] and parent_st['acltype'] == 'NFS4':
                acl_to_set = await self.middleware.call('filesystem.get_inherited_acl', {
                    'path': os.path.join('/mnt', parent_name),
                })
            else:
                acl_to_set = (await self.middleware.call('filesystem.acltemplate.by_path', {
                    'query-filters': [('name', '=', 'NFS4_RESTRICTED')],
                    'format-options': {'canonicalize': True, 'ensure_builtins': True},
                }))[0]['acl']

            acl_to_set.append({
                'tag': 'USER',
                'id': 568,
                'perms': {'BASIC': 'MODIFY'},
                'flags': {'BASIC': 'INHERIT'},
                'type': 'ALLOW'
            })
        elif data['share_type'] in ('MULTIPROTOCOL', 'NFS'):
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

        if data['type'] == 'FILESYSTEM' and data.get('acltype', 'INHERIT') != 'INHERIT':
            data['aclinherit'] = 'PASSTHROUGH' if data['acltype'] == 'NFSV4' else 'DISCARD'

        if parent_ds['locked']:
            verrors.add(
                'pool_dataset_create.name',
                f'{data["name"].rsplit("/", 1)[0]} must be unlocked to create {data["name"]}.'
            )

        encryption_dict = {}
        inherit_encryption_properties = data.pop('inherit_encryption')
        if not inherit_encryption_properties:
            encryption_dict = {'encryption': 'off'}

        unencrypted_parent = False
        for parent in get_dataset_parents(data['name']):
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
                elif data['encryption'] is False and not inherit_encryption_properties:
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

        if data['encryption']:
            if inherit_encryption_properties:
                verrors.add('pool_dataset_create.inherit_encryption', 'Must be disabled when encryption is enabled.')

            if not data['encryption_options']['passphrase']:
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

        props = {}
        for i, real_name, transform, inheritable in (
            ('aclinherit', None, str.lower, True),
            ('aclmode', None, str.lower, True),
            ('acltype', None, str.lower, True),
            ('atime', None, str.lower, True),
            ('casesensitivity', None, str.lower, True),
            ('checksum', None, str.lower, True),
            ('comments', TNUserProp.DESCRIPTION.value, None, True),
            ('compression', None, str.lower, True),
            ('copies', None, str, True),
            ('deduplication', 'dedup', str.lower, True),
            ('exec', None, str.lower, True),
            ('managedby', TNUserProp.MANAGED_BY.value, None, True),
            ('quota', None, none_normalize, True),
            ('quota_warning', TNUserProp.QUOTA_WARN.value, str, True),
            ('quota_critical', TNUserProp.QUOTA_CRIT.value, str, True),
            ('readonly', None, str.lower, True),
            ('recordsize', None, None, True),
            ('refquota', None, none_normalize, True),
            ('refquota_warning', TNUserProp.REFQUOTA_WARN.value, str, True),
            ('refquota_critical', TNUserProp.REFQUOTA_CRIT.value, str, True),
            ('refreservation', None, none_normalize, False),
            ('reservation', None, none_normalize, False),
            ('snapdir', None, str.lower, True),
            ('snapdev', None, str.lower, True),
            ('sparse', None, None, False),
            ('sync', None, str.lower, True),
            ('volblocksize', None, None, False),
            ('volsize', None, lambda x: str(x), False),
            ('special_small_block_size', 'special_small_blocks', None, True),
        ):
            if i not in data or (inheritable and data[i] == 'INHERIT'):
                continue
            name = real_name or i
            props[name] = data[i] if not transform else transform(data[i])

        props.update(
            **encryption_dict,
            **(await self.get_create_update_user_props(data['user_properties']))
        )

        await self.middleware.call('zfs.dataset.create', {
            'name': data['name'],
            'type': data['type'],
            'properties': props,
            'create_ancestors': data['create_ancestors'],
        })

        dataset_data = {
            'name': data['name'], 'encryption_key': encryption_dict.get('key'),
            'key_format': encryption_dict.get('keyformat')
        }
        await self.middleware.call('pool.dataset.insert_or_update_encrypted_record', dataset_data)
        await self.middleware.call_hook('dataset.post_create', {'encrypted': bool(encryption_dict), **dataset_data})

        data['id'] = data['name']

        await self.middleware.call('zfs.dataset.mount', data['name'])

        created_ds = await self.get_instance(data['id'])

        if acl_to_set:
            # We're potentially auto-inheriting an ACL containing nested
            # security groups and so we need to skip the ACL validation
            acl_job = await self.middleware.call('filesystem.setacl', {
                'path': mountpoint,
                'dacl': acl_to_set,
                'options': {'validate_effective_acl': False}
            })
            await acl_job.wait(raise_error=True)

        self.middleware.send_event('pool.dataset.query', 'ADDED', id=data['id'], fields=created_ds)
        return created_ds

    @api_method(PoolDatasetUpdateArgs, PoolDatasetUpdateResult, audit='Pool dataset update', audit_callback=True)
    async def do_update(self, audit_callback, id_, data):
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
            await self.__common_validation(verrors, 'pool_dataset_update', data, 'UPDATE', cur_dataset=dataset[0])
            if 'volsize' in data:
                if data['volsize'] < dataset[0]['volsize']['parsed']:
                    verrors.add('pool_dataset_update.volsize',
                                'You cannot shrink a zvol from GUI, this may lead to data loss.')
            if dataset[0]['type'] == 'VOLUME':
                existing_snapdev_prop = dataset[0]['snapdev']['parsed'].upper()
                snapdev_prop = data.get('snapdev') or existing_snapdev_prop
                if existing_snapdev_prop != snapdev_prop and snapdev_prop in ('INHERIT', 'HIDDEN'):
                    if await self.middleware.call(
                        'zfs.dataset.unlocked_zvols_fast',
                        [['attachment', '!=', None], ['ro', '=', True], ['name', '^', f'{id_}@']],
                        {}, ['RO', 'ATTACHMENT']
                    ):
                        verrors.add(
                            'pool_dataset_update.snapdev',
                            f'{id_!r} has snapshots which have attachments being used. Before marking it '
                            'as HIDDEN, remove attachment usages.'
                        )
        else:
            verrors.add('id', f'{id_} does not exist', errno.ENOENT)

        verrors.check()

        properties_definitions = (
            ('aclinherit', None, str.lower, True),
            ('aclmode', None, str.lower, True),
            ('acltype', None, str.lower, True),
            ('atime', None, str.lower, True),
            ('checksum', None, str.lower, True),
            ('comments', TNUserProp.DESCRIPTION.value, None, False),
            ('sync', None, str.lower, True),
            ('compression', None, str.lower, True),
            ('deduplication', 'dedup', str.lower, True),
            ('exec', None, str.lower, True),
            ('managedby', TNUserProp.MANAGED_BY.value, None, True),
            ('quota', None, none_normalize, False),
            ('quota_warning', TNUserProp.QUOTA_WARN.value, str, True),
            ('quota_critical', TNUserProp.QUOTA_CRIT.value, str, True),
            ('refquota', None, none_normalize, False),
            ('refquota_warning', TNUserProp.REFQUOTA_WARN.value, str, True),
            ('refquota_critical', TNUserProp.REFQUOTA_CRIT.value, str, True),
            ('reservation', None, none_normalize, False),
            ('refreservation', None, none_normalize, False),
            ('copies', None, str, True),
            ('snapdir', None, str.lower, True),
            ('snapdev', None, str.lower, True),
            ('readonly', None, str.lower, True),
            ('recordsize', None, None, True),
            ('volsize', None, lambda x: str(x), False),
            ('special_small_block_size', 'special_small_blocks', None, True),
        )

        props = {}
        for i, real_name, transform, inheritable in properties_definitions:
            if i not in data:
                continue
            name = real_name or i
            if inheritable and data[i] == 'INHERIT':
                props[name] = {'source': 'INHERIT'}
            else:
                props[name] = {'value': data[i] if not transform else transform(data[i])}

        if data.get('user_properties_update'):
            props.update(await self.get_create_update_user_props(data['user_properties_update'], True))

        if 'acltype' in props and (acltype_value := props['acltype'].get('value')):
            if acltype_value == 'nfsv4':
                props.update({
                    'aclinherit': {'value': 'passthrough'}
                })
            elif acltype_value in ['posix', 'off']:
                props.update({
                    'aclmode': {'value': 'discard'},
                    'aclinherit': {'value': 'discard'}
                })
            elif props['acltype'].get('source') == 'INHERIT':
                props.update({
                    'aclmode': {'source': 'INHERIT'},
                    'aclinherit': {'source': 'INHERIT'}
                })

        try:
            await self.middleware.call('zfs.dataset.update', id_, {'properties': props})
        except ZFSSetPropertyError as e:
            verrors = ValidationErrors()
            verrors.add_child('pool_dataset_update', self.__handle_zfs_set_property_error(e, properties_definitions))
            raise verrors

        if data['type'] == 'VOLUME':
            if 'volsize' in data and data['volsize'] > dataset[0]['volsize']['parsed']:
                # means the zvol size has increased so we need to check if this zvol is shared via SCST (iscsi)
                # and if it is, resync it so the connected initiators can see the new size of the zvol
                await self.middleware.call('iscsi.global.resync_lun_size_for_zvol', id_)

            if 'readonly' in data:
                # depending on the iscsi client connected to us, if someone marks a zvol
                # as R/O (or R/W), we need to be sure and update the associated extent so
                # that we don't get into a scenario where the iscsi extent is R/W but the
                # underlying zvol is R/O. Windows clients seem to not handle this very well.
                await self.middleware.call('iscsi.global.resync_readonly_property_for_zvol', id_, data['readonly'])

        updated_ds = await self.get_instance(id_)
        self.middleware.send_event('pool.dataset.query', 'CHANGED', id=id_, fields=updated_ds)
        return updated_ds

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

        if not options['recursive'] and await self.middleware.call('zfs.dataset.query', [['id', '^', f'{id_}/']]):
            raise CallError(
                f'Failed to delete dataset: cannot destroy {id_!r}: filesystem has children', errno.ENOTEMPTY
            )

        dataset = await self.get_instance(id_)
        audit_callback(dataset['name'])
        if mountpoint := dataset_mountpoint(dataset):
            for delegate in await self.middleware.call('pool.dataset.get_attachment_delegates'):
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

        result = await self.middleware.call('zfs.dataset.delete', id_, {
            'force': options['force'],
            'recursive': options['recursive'],
        })
        return result

    # Used by Democratic CSI
    # FIXME: phase it out
    @api_method(
        PoolDatasetDestroySnapshotsArgs,
        PoolDatasetDestroySnapshotsResult,
        roles=['SNAPSHOT_WRITE'],
        removed_in="v26.04",
    )
    @job(lock=lambda args: f'destroy_snapshots_{args[0]}')
    async def destroy_snapshots(self, job, name, snapshots_spec):
        """
        Destroy specified snapshots of a given dataset.
        """
        await self.get_instance(name, {'extra': {
            'properties': [],
            'retrieve_children': False,
        }})

        verrors = ValidationErrors()
        schema_name = 'destroy_snapshots'
        if snapshots_spec['all'] and snapshots_spec['snapshots']:
            verrors.add(
                f'{schema_name}.snapshots', 'Must not be specified when all snapshots are specified for removal'
            )
        else:
            for i, entry in enumerate(snapshots_spec['snapshots']):
                if not entry:
                    verrors.add(f'{schema_name}.snapshots.{i}', 'Either "start" or "end" must be specified')

        verrors.check()

        job.set_progress(20, 'Initial validation complete')

        return await self.middleware.call('zfs.dataset.destroy_snapshots', name, snapshots_spec)

    def __handle_zfs_set_property_error(self, e, properties_definitions):
        zfs_name_to_api_name = {i[1]: i[0] for i in properties_definitions}
        api_name = zfs_name_to_api_name.get(e.property) or e.property
        verrors = ValidationErrors()
        verrors.add(api_name, e.error)
        return verrors

    @item_method
    @api_method(PoolDatasetPromoteArgs, PoolDatasetPromoteResult, roles=['DATASET_WRITE'])
    async def promote(self, id_):
        """
        Promote the cloned dataset `id`.
        """
        dataset = await self.middleware.call('zfs.dataset.query', [('id', '=', id_)])
        if not dataset:
            raise CallError(f'Dataset "{id_}" does not exist.', errno.ENOENT)
        if not dataset[0]['properties']['origin']['value']:
            raise CallError('Only cloned datasets can be promoted.', errno.EBADMSG)
        return await self.middleware.call('zfs.dataset.promote', id_)

    @api_method(
        PoolDatasetRenameArgs,
        PoolDatasetRenameResult,
        audit='Pool dataset rename from',
        audit_extended=lambda id_, options: f'{id_!r} to {options["new_name"]!r}',
        roles=['DATASET_WRITE']
    )
    async def rename(self, id_, options):
        """
        Rename a pool dataset `id`.

        No safety checks are performed when renaming ZFS resources. If the dataset is in use by services such
        as SMB, iSCSI, snapshot tasks, replication, or cloud sync, renaming may cause disruptions or service failures.

        Proceed only if you are certain the ZFS resource is not in use and fully understand the risks.
        Set Force to continue.
        """
        if not options['force']:
            raise ValidationError(
                'pool.dataset.rename.force',
                'No safety checks are performed when renaming ZFS resources; this may break existing usages. '
                'If you understand the risks, please set force and proceed.'
            )

        return await self.middleware.call('zfs.dataset.rename', id_, options)
