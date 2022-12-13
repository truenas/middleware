import copy
import errno
import os

import middlewared.sqlalchemy as sa

from middlewared.plugins.zfs import ZFSSetPropertyError
from middlewared.plugins.zfs_.validation_utils import validate_dataset_name
from middlewared.schema import (
    accepts, Any, Attribute, EnumMixin, Bool, Dict, Int, List, NOT_PROVIDED, Patch, Ref, returns, Str
)
from middlewared.service import (
    CallError, CRUDService, filterable, item_method, job, pass_app, private, ValidationErrors
)
from middlewared.utils import filter_list
from middlewared.validators import Exact, Match, Or, Range

from .utils import (
    attachments_path, get_props_of_interest_mapping, none_normalize, ZFS_COMPRESSION_ALGORITHM_CHOICES,
    ZFS_CHECKSUM_CHOICES, ZFSKeyFormat, ZFS_MAX_DATASET_NAME_LEN,
)


class Inheritable(EnumMixin, Attribute):
    def __init__(self, schema, **kwargs):
        self.schema = schema
        if not self.schema.has_default and 'default' not in kwargs and kwargs.pop('has_default', True):
            kwargs['default'] = 'INHERIT'
        super(Inheritable, self).__init__(self.schema.name, **kwargs)

    def clean(self, value):
        if value == 'INHERIT':
            return value
        elif value is NOT_PROVIDED and self.has_default:
            return copy.deepcopy(self.default)

        return self.schema.clean(value)

    def validate(self, value):
        if value == 'INHERIT':
            return

        return self.schema.validate(value)

    def to_json_schema(self, parent=None):
        schema = self.schema.to_json_schema(parent)
        type_schema = schema.pop('type')
        schema['nullable'] = 'null' in type_schema
        if schema['nullable']:
            type_schema.remove('null')
            if len(type_schema) == 1:
                type_schema = type_schema[0]
        schema['anyOf'] = [{'type': type_schema}, {'type': 'string', 'enum': ['INHERIT']}]
        return schema


class PoolDatasetEncryptionModel(sa.Model):
    __tablename__ = 'storage_encrypteddataset'

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(255))
    encryption_key = sa.Column(sa.EncryptedText(), nullable=True)
    kmip_uid = sa.Column(sa.String(255), nullable=True, default=None)


class PoolDatasetService(CRUDService):

    ENTRY = Dict(
        'pool_dataset_entry',
        Str('id', required=True),
        Str('type', required=True),
        Str('name', required=True),
        Str('pool', required=True),
        Bool('encrypted'),
        Str('encryption_root', null=True),
        Bool('key_loaded', null=True),
        List('children', required=True),
        Dict('user_properties', additional_attrs=True, required=True),
        Bool('locked'),
        *[Dict(
            p[1] or p[0],
            Any('parsed', null=True),
            Str('rawvalue', null=True),
            Str('value', null=True),
            Str('source', null=True),
            Any('source_info', null=True),
        ) for p in get_props_of_interest_mapping() if (p[1] or p[0]) != 'mountpoint'],
        Str('mountpoint', null=True),
    )

    class Config:
        cli_namespace = 'storage.dataset'
        datastore_primary_key_type = 'string'
        event_send = False
        namespace = 'pool.dataset'

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
        return [
            'org.freenas:description',
            'org.freenas:quota_warning',
            'org.freenas:quota_critical',
            'org.freenas:refquota_warning',
            'org.freenas:refquota_critical',
            'org.truenas:managedby',
        ]

    def __transform(self, datasets, retrieve_children, children_filters):
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
            ['pool', '!=', await self.middleware.call('boot.pool_name')],
            ['id', 'rnin', '/.system'],
            ['id', 'rnin', '/.glusterfs'],
            ['id', 'rnin', '/ix-applications/'],
        ]

    @private
    async def is_internal_dataset(self, dataset):
        return not bool(filter_list([{'id': dataset}], await self.internal_datasets_filters()))

    @filterable
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
        If no properties are desired, in that case an empty list should be sent.

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
        if len(filters) == 1 and len(filters[0]) == 3 and list(filters[0][:2]) == ['id', '=']:
            zfsfilters.append(copy.deepcopy(filters[0]))

        internal_datasets_filters = self.middleware.call_sync('pool.dataset.internal_datasets_filters')
        filters.extend(internal_datasets_filters)
        extra = copy.deepcopy(options.get('extra', {}))
        retrieve_children = extra.get('retrieve_children', True)
        props = extra.get('properties')
        snapshots = extra.get('snapshots')
        snapshots_recursive = extra.get('snapshots_recursive')
        snapshots_count = extra.get('snapshots_count')
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
                        'snapshots_properties': extra.get('snapshots_properties', [])
                    }
                }
            ), retrieve_children, internal_datasets_filters,
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

        if parent is None:
            parent = await self.middleware.call(
                'pool.dataset.query',
                [('id', '=', data['name'].rsplit('/', 1)[0])],
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
                verrors.add(f'{schema}.name', 'Parent dataset does not exist for specified name')
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

        if data['type'] == 'FILESYSTEM':
            if data.get('acltype', 'INHERIT') != 'INHERIT' or data.get('aclmode', 'INHERIT') != 'INHERIT':
                to_check = data.copy()
                check_ds = cur_dataset if mode == 'UPDATE' else parent
                if data.get('aclmode', 'INHERIT') == 'INHERIT':
                    to_check['aclmode'] = check_ds['aclmode']['value']

                if data.get('acltype', 'INHERIT') == 'INHERIT':
                    to_check['acltype'] = check_ds['acltype']['value']

                acltype = to_check.get('acltype', 'POSIX')
                if acltype in ['POSIX', 'OFF'] and to_check.get('aclmode', 'DISCARD') != 'DISCARD':
                    verrors.add(f'{schema}.aclmode', 'Must be set to DISCARD when acltype is POSIX or OFF')

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
                if rs != 'INHERIT' and rs not in await self.middleware.call('pool.dataset.recordsize_choices'):
                    verrors.add(f'{schema}.recordsize', f'{rs!r} is an invalid recordsize.')

        elif data['type'] == 'VOLUME':
            if mode == 'CREATE' and 'volsize' not in data:
                verrors.add(f'{schema}.volsize', 'This field is required for VOLUME')

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

    @accepts(Dict(
        'pool_dataset_create',
        Str('name', required=True),
        Str('type', enum=['FILESYSTEM', 'VOLUME'], default='FILESYSTEM'),
        Int('volsize'),  # IN BYTES
        Str('volblocksize', enum=[
            '512', '512B', '1K', '2K', '4K', '8K', '16K', '32K', '64K', '128K',
        ]),
        Bool('sparse'),
        Bool('force_size'),
        Inheritable(Str('comments')),
        Inheritable(Str('sync', enum=['STANDARD', 'ALWAYS', 'DISABLED'])),
        Inheritable(Str('snapdev', enum=['HIDDEN', 'VISIBLE']), has_default=False),
        Inheritable(Str('compression', enum=ZFS_COMPRESSION_ALGORITHM_CHOICES)),
        Inheritable(Str('atime', enum=['ON', 'OFF']), has_default=False),
        Inheritable(Str('exec', enum=['ON', 'OFF'])),
        Inheritable(Str('managedby', empty=False)),
        Int('quota', null=True, validators=[Or(Range(min=1024 ** 3), Exact(0))]),
        Inheritable(Int('quota_warning', validators=[Range(0, 100)])),
        Inheritable(Int('quota_critical', validators=[Range(0, 100)])),
        Int('refquota', null=True, validators=[Or(Range(min=1024 ** 3), Exact(0))]),
        Inheritable(Int('refquota_warning', validators=[Range(0, 100)])),
        Inheritable(Int('refquota_critical', validators=[Range(0, 100)])),
        Int('reservation'),
        Int('refreservation'),
        Inheritable(Int('special_small_block_size'), has_default=False),
        Inheritable(Int('copies')),
        Inheritable(Str('snapdir', enum=['VISIBLE', 'HIDDEN'])),
        Inheritable(Str('deduplication', enum=['ON', 'VERIFY', 'OFF'])),
        Inheritable(Str('checksum', enum=ZFS_CHECKSUM_CHOICES)),
        Inheritable(Str('readonly', enum=['ON', 'OFF'])),
        Inheritable(Str('recordsize'), has_default=False),
        Inheritable(Str('casesensitivity', enum=['SENSITIVE', 'INSENSITIVE']), has_default=False),
        Inheritable(Str('aclmode', enum=['PASSTHROUGH', 'RESTRICTED', 'DISCARD']), has_default=False),
        Inheritable(Str('acltype', enum=['OFF', 'NFSV4', 'POSIX']), has_default=False),
        Str('share_type', default='GENERIC', enum=['GENERIC', 'SMB']),
        Inheritable(Str('xattr', default='SA', enum=['ON', 'SA'])),
        Ref('encryption_options'),
        Bool('encryption', default=False),
        Bool('inherit_encryption', default=True),
        List(
            'user_properties',
            items=[Dict(
                'user_property',
                Str('key', required=True, validators=[Match(r'.*:.*')]),
                Str('value', required=True),
            )],
        ),
        Bool('create_ancestors', default=False),
        register=True,
    ))
    @pass_app(rest=True)
    async def do_create(self, app, data):
        """
        Creates a dataset/zvol.

        `volsize` is required for type=VOLUME and is supposed to be a multiple of the block size.
        `sparse` and `volblocksize` are only used for type=VOLUME.

        `encryption` when enabled will create an ZFS encrypted root dataset for `name` pool.
        There are 2 cases where ZFS encryption is not allowed for a dataset:
        1) Pool in question is GELI encrypted.
        2) If the parent dataset is encrypted with a passphrase and `name` is being created
           with a key for encrypting the dataset.

        `encryption_options` specifies configuration for encryption of dataset for `name` pool.
        `encryption_options.passphrase` must be specified if encryption for dataset is desired with a passphrase
        as a key.
        Otherwise a hex encoded key can be specified by providing `encryption_options.key`.
        `encryption_options.generate_key` when enabled automatically generates the key to be used
        for dataset encryption.

        It should be noted that keys are stored by the system for automatic locking/unlocking
        on import/export of encrypted datasets. If that is not desired, dataset should be created
        with a passphrase as a key.

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

        if '/' not in data['name']:
            verrors.add('pool_dataset_create.name', 'You need a full name, e.g. pool/newdataset')
        elif not validate_dataset_name(data['name']):
            verrors.add('pool_dataset_create.name', 'Invalid dataset name')
        elif len(data['name']) > ZFS_MAX_DATASET_NAME_LEN:
            verrors.add(
                'pool_dataset_create.name',
                f'Dataset name length should be less than or equal to {ZFS_MAX_DATASET_NAME_LEN}',
            )
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
            await self.__common_validation(verrors, 'pool_dataset_create', data, 'CREATE', parent_ds)

        verrors.check()

        parent_ds = parent_ds[0]
        mountpoint = os.path.join('/mnt', data['name'])
        if data['type'] == 'FILESYSTEM' and data.get('acltype', 'INHERIT') == 'INHERIT' and len(
                data['name'].split('/')
        ) == 2:
            data['acltype'] = 'POSIX'

        if os.path.exists(mountpoint):
            verrors.add('pool_dataset_create.name', f'Path {mountpoint} already exists')

        if data['share_type'] == 'SMB':
            data['casesensitivity'] = 'INSENSITIVE'
            data['acltype'] = 'NFSV4'
            data['aclmode'] = 'RESTRICTED'

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

        if data['encryption']:
            if inherit_encryption_properties:
                verrors.add('pool_dataset_create.inherit_encryption', 'Must be disabled when encryption is enabled.')
            if (
                    await self.middleware.call('pool.query', [['name', '=', data['name'].split('/')[0]]], {'get': True})
            )['encrypt']:
                verrors.add(
                    'pool_dataset_create.encryption',
                    'Encrypted datasets cannot be created on a GELI encrypted pool.'
                )

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

        if app:
            uri = None
            if app.rest and app.host:
                uri = app.host
            elif app.websocket and app.request.headers.get('X-Real-Remote-Addr'):
                uri = app.request.headers.get('X-Real-Remote-Addr')
            if uri and uri not in [
                '::1', '127.0.0.1', *[d['address'] for d in await self.middleware.call('interface.ip_in_use')]
            ]:
                data['managedby'] = uri if not data['managedby'] != 'INHERIT' else f'{data["managedby"]}@{uri}'

        props = {}
        for i, real_name, transform, inheritable in (
            ('aclinherit', None, str.lower, True),
            ('aclmode', None, str.lower, True),
            ('acltype', None, str.lower, True),
            ('atime', None, str.lower, True),
            ('casesensitivity', None, str.lower, True),
            ('checksum', None, str.lower, True),
            ('comments', 'org.freenas:description', None, True),
            ('compression', None, str.lower, True),
            ('copies', None, str, True),
            ('deduplication', 'dedup', str.lower, True),
            ('exec', None, str.lower, True),
            ('managedby', 'org.truenas:managedby', None, True),
            ('quota', None, none_normalize, True),
            ('quota_warning', 'org.freenas:quota_warning', str, True),
            ('quota_critical', 'org.freenas:quota_critical', str, True),
            ('readonly', None, str.lower, True),
            ('recordsize', None, None, True),
            ('refquota', None, none_normalize, True),
            ('refquota_warning', 'org.freenas:refquota_warning', str, True),
            ('refquota_critical', 'org.freenas:refquota_critical', str, True),
            ('refreservation', None, none_normalize, False),
            ('reservation', None, none_normalize, False),
            ('snapdir', None, str.lower, True),
            ('snapdev', None, str.lower, True),
            ('sparse', None, None, False),
            ('sync', None, str.lower, True),
            ('volblocksize', None, None, False),
            ('volsize', None, lambda x: str(x), False),
            ('xattr', None, str.lower, True),
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

        if data['type'] == 'FILESYSTEM' and data['share_type'] == 'SMB' and created_ds['acltype']['value'] == "NFSV4":
            acl_job = await self.middleware.call(
                'pool.dataset.permission', data['id'], {'options': {'set_default_acl': True}}
            )
            await acl_job.wait()

        return created_ds

    @accepts(Str('id', required=True), Patch(
        'pool_dataset_create', 'pool_dataset_update',
        ('rm', {'name': 'name'}),
        ('rm', {'name': 'type'}),
        ('rm', {'name': 'casesensitivity'}),  # Its a readonly attribute
        ('rm', {'name': 'share_type'}),  # This is something we should only do at create time
        ('rm', {'name': 'sparse'}),  # Create time only attribute
        ('rm', {'name': 'volblocksize'}),  # Create time only attribute
        ('rm', {'name': 'encryption'}),  # Create time only attribute
        ('rm', {'name': 'encryption_options'}),  # Create time only attribute
        ('rm', {'name': 'inherit_encryption'}),  # Create time only attribute
        ('add', List(
            'user_properties_update',
            items=[Dict(
                'user_property',
                Str('key', required=True, validators=[Match(r'.*:.*')]),
                Str('value'),
                Bool('remove'),
            )],
        )),
        ('attr', {'update': True}),
    ))
    async def do_update(self, id, data):
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
            'pool.dataset.query', [('id', '=', id)], {'extra': {'retrieve_children': False}}
        )
        if not dataset:
            verrors.add('id', f'{id} does not exist', errno.ENOENT)
        else:
            data['type'] = dataset[0]['type']
            data['name'] = dataset[0]['name']
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
                        [['attachment', '!=', None], ['ro', '=', True], ['name', '^', f'{id}@']],
                        {}, ['RO', 'ATTACHMENT']
                    ):
                        verrors.add(
                            'pool_dataset_update.snapdev',
                            f'{id!r} has snapshots which have attachments being used. Before marking it '
                            'as HIDDEN, remove attachment usages.'
                        )

        verrors.check()

        properties_definitions = (
            ('aclinherit', None, str.lower, True),
            ('aclmode', None, str.lower, True),
            ('acltype', None, str.lower, True),
            ('atime', None, str.lower, True),
            ('checksum', None, str.lower, True),
            ('comments', 'org.freenas:description', None, False),
            ('sync', None, str.lower, True),
            ('compression', None, str.lower, True),
            ('deduplication', 'dedup', str.lower, True),
            ('exec', None, str.lower, True),
            ('managedby', 'org.truenas:managedby', None, True),
            ('quota', None, none_normalize, False),
            ('quota_warning', 'org.freenas:quota_warning', str, True),
            ('quota_critical', 'org.freenas:quota_critical', str, True),
            ('refquota', None, none_normalize, False),
            ('refquota_warning', 'org.freenas:refquota_warning', str, True),
            ('refquota_critical', 'org.freenas:refquota_critical', str, True),
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
            await self.middleware.call('zfs.dataset.update', id, {'properties': props})
        except ZFSSetPropertyError as e:
            verrors = ValidationErrors()
            verrors.add_child('pool_dataset_update', self.__handle_zfs_set_property_error(e, properties_definitions))
            raise verrors

        if data['type'] == 'VOLUME' and 'volsize' in data and data['volsize'] > dataset[0]['volsize']['parsed']:
            # means the zvol size has increased so we need to check if this zvol is shared via SCST (iscs)
            # and if it is, resync it so the connected initiators can see the new size of the zvol
            await self.middleware.call('iscsi.global.resync_lun_size_for_zvol', id)

        return await self.get_instance(id)

    @accepts(Str('id'), Dict(
        'dataset_delete',
        Bool('recursive', default=False),
        Bool('force', default=False),
    ))
    async def do_delete(self, id, options):
        """
        Delete dataset/zvol `id`.

        `recursive` will also delete/destroy all children datasets.
        `force` will force delete busy datasets.

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

        if not options['recursive'] and await self.middleware.call('zfs.dataset.query', [['id', '^', f'{id}/']]):
            raise CallError(
                f'Failed to delete dataset: cannot destroy {id!r}: filesystem has children', errno.ENOTEMPTY
            )

        dataset = await self.get_instance(id)
        path = attachments_path(dataset)
        if path:
            for delegate in await self.middleware.call('pool.dataset.get_attachment_delegates'):
                attachments = await delegate.query(path, True)
                if attachments:
                    await delegate.delete(attachments)

        if dataset['locked'] and dataset['mountpoint'] and os.path.exists(dataset['mountpoint']):
            # We would like to remove the immutable flag in this case so that it's mountpoint can be
            # cleaned automatically when we delete the dataset
            await self.middleware.call('filesystem.set_immutable', False, dataset['mountpoint'])

        result = await self.middleware.call('zfs.dataset.delete', id, {
            'force': options['force'],
            'recursive': options['recursive'],
        })
        return result

    @accepts(
        Str('name'),
        Dict(
            'snapshots',
            Bool('all', default=True),
            Bool('recursive', default=False),
            List(
                'snapshots', items=[Dict(
                    'snapshot_spec',
                    Str('start'),
                    Str('end'),
                ), Str('snapshot_name')]
            ),
        ),
    )
    @returns(List('deleted_snapshots', items=[Str('deleted_snapshot')]))
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
    @accepts(Str('id'))
    @returns()
    async def promote(self, id):
        """
        Promote the cloned dataset `id`.
        """
        dataset = await self.middleware.call('zfs.dataset.query', [('id', '=', id)])
        if not dataset:
            raise CallError(f'Dataset "{id}" does not exist.', errno.ENOENT)
        if not dataset[0]['properties']['origin']['value']:
            raise CallError('Only cloned datasets can be promoted.', errno.EBADMSG)
        return await self.middleware.call('zfs.dataset.promote', id)
