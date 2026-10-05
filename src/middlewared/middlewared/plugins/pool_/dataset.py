import errno

from pydantic import ValidationError as PydanticValidationError

from middlewared.api import api_method
from middlewared.api.current import (
    PoolDatasetCreateArgs,
    PoolDatasetCreateResult,
    PoolDatasetDeleteArgs,
    PoolDatasetDeleteResult,
    PoolDatasetEntry,
    PoolDatasetPromoteArgs,
    PoolDatasetPromoteResult,
    PoolDatasetRenameArgs,
    PoolDatasetRenameResult,
    PoolDatasetUpdateArgs,
    PoolDatasetUpdateResult,
    ZFSResourceCreateArgsData,
    ZFSResourceDestroyArgsData,
    ZFSResourcePromoteArgsData,
    ZFSResourceQuery,
    ZFSResourceRenameArgsData,
    ZFSResourceSetArgsData,
)
from middlewared.plugins.zfs.share_presets import SHARE_PRESETS
from middlewared.plugins.zfs.utils import has_internal_path
from middlewared.service import (
    CallError,
    CRUDService,
    InstanceNotFound,
    ValidationError,
    ValidationErrors,
    filterable_api_method,
    private,
)
from middlewared.utils.boot.pool import BOOT_POOL_NAME_VALID
from middlewared.utils.filter_list import filter_list

from .dataset_query_utils import generic_query, is_internal_dataset_name, user_property_names_to_be_renamed
from .utils import (
    POOL_DS_CREATE_PROPERTIES,
    POOL_DS_UPDATE_PROPERTIES,
    RE_ZFS_USER_PROP,
    ZFS_USER_PROP_MAX_LEN,
    UpdateImplArgs,
    get_dataset_parents,
    pool_dataset_view,
)


def validate_user_properties(verrors, schema, user_properties):
    """Reject user property keys that TrueNAS manages or that ZFS will not accept.

    A property TrueNAS manages may still be removed, since that is the only way to
    drop one that a previous release wrote out.

    Args:
        verrors: ValidationErrors instance to add any error to.
        schema: Schema name of the list being validated.
        user_properties: List of user properties, each with at least a `key`.
    """
    managed = user_property_names_to_be_renamed()
    seen = set()
    for index, prop in enumerate(user_properties):
        prop_schema = f'{schema}.{index}.key'
        if (key := prop['key']) in managed and not prop.get('remove'):
            verrors.add(prop_schema, f'{key!r} is managed by TrueNAS, use the {managed[key]!r} field to set it.')
        elif len(key) > ZFS_USER_PROP_MAX_LEN or not RE_ZFS_USER_PROP.fullmatch(key):
            verrors.add(prop_schema, f'{key!r} is not a valid ZFS user property name.')
        elif key in seen:
            verrors.add(prop_schema, f'{key!r} is specified more than once.')
        else:
            seen.add(key)


def _native_value(prop, value):
    if prop.is_user_prop:
        return prop.transform(value) if prop.transform else value
    elif prop.transform is str.lower:
        return value.lower()
    else:
        return 0 if value is None else value


def _pool_field(api_names, sent, name):
    if api_names.get(name) in sent:
        return api_names[name]
    if name in ('aclmode', 'aclinherit'):
        return 'acltype'
    if name == 'refreservation' and 'volsize' in sent:
        return 'volsize'
    if name not in api_names:
        return 'user_properties_update' if 'user_properties_update' in sent else 'user_properties'
    return None


def translate_update(data):
    properties, user_properties, inherit = {}, {}, []
    for prop in POOL_DS_UPDATE_PROPERTIES:
        if prop.api_name not in data:
            continue
        value = data[prop.api_name]
        if prop.inheritable and value == 'INHERIT':
            inherit.append(prop.real_name)
        elif prop.is_user_prop:
            user_properties[prop.real_name] = _native_value(prop, value)
        else:
            properties[prop.real_name] = _native_value(prop, value)

    for up in data.get('user_properties_update', []):
        if 'value' in up:
            user_properties[up['key']] = up['value']
        elif up.get('remove'):
            inherit.append(up['key'])

    return properties, user_properties, inherit


def rekey_update_errors(verrors, sent, errors):
    """Add `zfs.resource.set` errors to `verrors` under the `pool_dataset_update` field the caller sent."""
    api_names = {prop.real_name: prop.api_name for prop in POOL_DS_UPDATE_PROPERTIES}

    for attribute, errmsg, errno_ in errors:
        section, _, name = attribute.removeprefix('zfs.resource.set.').partition('.')
        if section == 'properties' and name:
            field = _pool_field(api_names, sent, name.split('.', 1)[0])
        elif section == 'inherit' and name:
            field = _pool_field(api_names, sent, name)
        elif section == 'user_properties':
            field = next((f for f in ('user_properties_update', 'user_properties') if f in sent), None)
        else:
            field = None
        verrors.add(f'pool_dataset_update.{field}' if field else 'pool_dataset_update', errmsg, errno_)


def translate_create(data):
    properties, user_properties = {}, {}
    for prop in POOL_DS_CREATE_PROPERTIES:
        value = data.get(prop.api_name, 'INHERIT')
        if value == 'INHERIT':
            continue
        if prop.is_user_prop:
            user_properties[prop.real_name] = _native_value(prop, value)
        else:
            properties[prop.real_name] = _native_value(prop, value)
    if data.get('sparse'):
        properties['refreservation'] = 0
    for up in data['user_properties']:
        user_properties[up['key']] = up['value']
    return properties, user_properties


def rekey_create_errors(verrors, sent, errors):
    api_names = {prop.real_name: prop.api_name for prop in POOL_DS_CREATE_PROPERTIES}
    for attribute, errmsg, errno_ in errors:
        section, _, name = attribute.removeprefix('zfs.resource.create').removeprefix('.').partition('.')
        if section in ('', 'path'):
            field = 'name'
        elif section == 'properties' and name:
            field = _pool_field(api_names, sent, name.split('.', 1)[0])
        elif section == 'encryption':
            field = f'encryption_options.{name}' if name else 'encryption'
        elif section in ('share_type', 'user_properties'):
            field = section
        else:
            field = None
        verrors.add(f'pool_dataset_create.{field}' if field else 'pool_dataset_create', errmsg, errno_)


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
        if is_internal_dataset_name(name):
            raise InstanceNotFound(f'PoolDataset {name} does not exist')
        encryption = bool((options or {}).get('encryption'))
        properties = ['mountpoint', 'encryption'] if encryption else ['mountpoint']
        rows = await self.call2(
            self.s.zfs.resource.list_impl, ZFSResourceQuery(paths=[name], properties=properties)
        )
        if not rows:
            raise InstanceNotFound(f'PoolDataset {name} does not exist')
        return pool_dataset_view(rows[0], encryption)

    @private
    async def internal_datasets_filters(self):
        # We get filters here which ensure that we don't match an internal dataset
        return [
            ['pool', 'nin', BOOT_POOL_NAME_VALID],
            ['id', 'rnin', '/.system'],
            ['id', 'rnin', '/ix-applications/'],
            ['id', 'rnin', '/ix-apps'],
        ]

    @private
    async def is_internal_dataset(self, dataset):
        pool = dataset.split('/')[0]
        return not bool(filter_list([{'id': dataset, 'pool': pool}], await self.internal_datasets_filters()))

    @filterable_api_method(
        item=PoolDatasetEntry,
        pass_thread_local_storage=True,
    )
    def query(self, tls, filters, options):
        """
        Query pool datasets with ``query-filters`` and ``query-options``.

        Results can be returned as a flat structure or as a hierarchy of top-level datasets with their children
        nested, controlled by the ``query-options.extra.flat`` option.

        The following ``query-options.extra`` options are supported:

        ``flat`` *(bool)*:
            Return all datasets as a flat list (``true``, the default) or only top-level datasets with their
            children nested under a ``children`` key (``false``).

        ``retrieve_children`` *(bool)*:
            Set to ``false`` to exclude child datasets from the results.

        ``properties`` *(list)*:
            List of ZFS properties to retrieve. ``null`` (the default) retrieves all properties; an empty list
            retrieves none, though user properties are still returned unless disabled.

        ``retrieve_user_props`` *(bool)*:
            Set to ``false`` to exclude ZFS user properties.

        ``snapshots`` *(bool)*:
            Include each dataset's snapshots in the results.

        ``snapshots_recursive`` *(bool)*:
            Include each dataset's snapshots recursively.

        ``snapshots_properties`` *(list)*:
            List of snapshot properties to retrieve.
        """
        extra = options.pop('extra', {})
        exclude_internal_datasets = extra.pop('exclude_internal_datasets', True)
        tier_enabled = self.call_sync2(self.s.zfs.tier.config).enabled

        return generic_query(
            tls.lzh.iter_root_filesystems,
            filters,
            options,
            extra,
            exclude_internal_datasets=exclude_internal_datasets,
            tier_enabled=tier_enabled,
        )

    async def __update_validation(self, verrors, schema, data, cur_dataset):
        if data['type'] == 'FILESYSTEM':
            for i in ('force_size', 'sparse', 'volsize', 'volblocksize'):
                if i in data:
                    verrors.add(f'{schema}.{i}', 'This field is not valid for FILESYSTEM')

        elif data['type'] == 'VOLUME':
            for i in (
                'aclmode', 'acltype', 'atime', 'casesensitivity', 'quota', 'refquota', 'recordsize',
            ):
                if i in data:
                    verrors.add(f'{schema}.{i}', 'This field is not valid for VOLUME')

        if data.get('user_properties_update') and not data.get('user_properties'):
            validate_user_properties(
                verrors, f'{schema}.user_properties_update', data['user_properties_update']
            )
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
            validate_user_properties(verrors, f'{schema}.user_properties', data['user_properties'])
            # Let's normalize this so that we create/update/remove user props accordingly.
            # The properties TrueNAS manages are reported under their API names (`comments`
            # and friends), which are not property names ZFS would accept, and they are owned
            # by their own fields, so they are never removed here.
            managed_user_props = set(user_property_names_to_be_renamed().values())
            user_props = {p['key'] for p in data['user_properties']}
            data['user_properties_update'] = data['user_properties']
            for prop_key in cur_dataset['user_properties']:
                if prop_key not in user_props and prop_key not in managed_user_props:
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

        Create a dataset within tank pool::

            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "pool.dataset.create",
                "params": [{
                    "name": "tank/myuser",
                    "comments": "Dataset for myuser"
                }]
            }
        """
        verrors = ValidationErrors()
        name = data['name']
        if await self.is_internal_dataset(name):
            verrors.add(
                'pool_dataset_create.name',
                f'{name!r} is using system internal managed dataset. Please specify a different parent.'
            )
        validate_user_properties(verrors, 'pool_dataset_create.user_properties', data['user_properties'])
        if data['encryption'] and data['inherit_encryption']:
            verrors.add('pool_dataset_create.inherit_encryption', 'Must be disabled when encryption is enabled.')
        elif not data['encryption'] and not data['inherit_encryption']:
            rows = await self.call2(
                self.s.zfs.resource.list_impl,
                ZFSResourceQuery(paths=get_dataset_parents(name), properties=['encryption']),
            )
            if rows and rows[0]['properties']['encryption']['raw'] != 'off':
                verrors.add(
                    'pool_dataset_create.encryption',
                    f'Cannot create an unencrypted dataset within an encrypted dataset ({rows[0]["name"]}).'
                )
        verrors.check()

        sent = {k for k, v in data.items() if v != 'INHERIT'}
        properties, user_properties = translate_create(data)
        share_type = None if data['share_type'] == 'GENERIC' else data['share_type'].lower()
        if share_type:
            for key in SHARE_PRESETS[share_type]:
                properties.pop(key, None)
        try:
            await self.call2(
                self.s.zfs.resource.create,
                ZFSResourceCreateArgsData(
                    path=name,
                    type=data['type'],
                    properties=properties,
                    user_properties=user_properties,
                    create_ancestors=data['create_ancestors'],
                    share_type=share_type,
                    encryption=data['encryption_options'] if data['encryption'] else None,
                    force_size=data.get('force_size', False),
                ),
            )
        except PydanticValidationError as e:
            rekey_create_errors(
                verrors, sent, [('.'.join(map(str, err['loc'])), err['msg'], errno.EINVAL) for err in e.errors()]
            )
        except ValidationError as e:
            rekey_create_errors(verrors, sent, [(e.attribute, e.errmsg, e.errno)])
        verrors.check()

        created_ds = await self.get_instance(name)
        self.middleware.send_event('pool.dataset.query', 'ADDED', id=name, fields=created_ds)
        return created_ds

    @private
    async def update_impl(self, data: UpdateImplArgs):
        await self.call2(
            self.s.zfs.resource.set_impl,
            ZFSResourceSetArgsData(
                path=data['name'],
                properties=data.get('zprops') or {},
                user_properties=data.get('uprops') or {},
                inherit=list(data.get('iprops') or ()),
                bypass=True,
            ),
        )

    @api_method(PoolDatasetUpdateArgs, PoolDatasetUpdateResult, audit='Pool dataset update', audit_callback=True)
    async def do_update(self, audit_callback, id_, data):
        """
        Updates a dataset/zvol ``id``.

        Update the ``comments`` for "tank/myuser"::

            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "pool.dataset.update",
                "params": ["tank/myuser", {
                    "comments": "Dataset for myuser, UPDATE #1"
                }]
            }
        """
        verrors = ValidationErrors()

        dataset = await self.middleware.call(
            'pool.dataset.query', [('id', '=', id_)], {'extra': {'retrieve_children': False}}
        )
        if not dataset:
            verrors.add('id', f'{id_} does not exist', errno.ENOENT)
            verrors.check()

        sent = set(data)
        data['type'] = dataset[0]['type']
        data['name'] = dataset[0]['name']
        audit_callback(data['name'])
        await self.__update_validation(verrors, 'pool_dataset_update', data, dataset[0])
        verrors.check()

        properties, user_properties, inherit = translate_update(data)
        if properties or user_properties or inherit:
            try:
                args = ZFSResourceSetArgsData(
                    path=data['name'],
                    properties=properties,
                    user_properties=user_properties,
                    inherit=inherit,
                    force_size=data.get('force_size', False),
                )
                await self.call2(self.s.zfs.resource.set, args)
            except PydanticValidationError as e:
                rekey_update_errors(
                    verrors, sent, [('.'.join(map(str, err['loc'])), err['msg'], errno.EINVAL) for err in e.errors()]
                )
            except ValidationError as e:
                rekey_update_errors(verrors, sent, [(e.attribute, e.errmsg, e.errno)])

        verrors.check()

        updated_ds = await self.get_instance(id_)
        self.middleware.send_event('pool.dataset.query', 'CHANGED', id=id_, fields=updated_ds)
        return updated_ds

    @api_method(PoolDatasetDeleteArgs, PoolDatasetDeleteResult, audit='Pool dataset delete', audit_callback=True)
    async def do_delete(self, audit_callback, id_, options):
        """
        Delete dataset/zvol ``id``.

        Delete "tank/myuser" dataset::

            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "pool.dataset.delete",
                "params": ["tank/myuser"]
            }
        """
        if has_internal_path(id_):
            raise ValidationError('pool.dataset.delete', f'{id_} is an invalid location')

        if not options['recursive']:
            ds = await self.call2(
                self.s.zfs.resource.list_impl,
                ZFSResourceQuery(paths=[id_], properties=None, get_children=True)
            )
            if len(ds) > 1:
                raise CallError(
                    f'Failed to delete dataset: cannot destroy {id_!r}: filesystem has children', errno.ENOTEMPTY
                )

        dataset = await self.get_instance_quick(id_)
        audit_callback(dataset['name'])

        await self.call2(
            self.s.zfs.resource.destroy,
            ZFSResourceDestroyArgsData(path=id_, recursive=options['recursive']),
        )
        return True

    @api_method(PoolDatasetPromoteArgs, PoolDatasetPromoteResult, roles=['DATASET_WRITE'])
    async def promote(self, id_):
        """Promote a cloned dataset."""
        return await self.call2(self.s.zfs.resource.promote, ZFSResourcePromoteArgsData(path=id_))

    @api_method(
        PoolDatasetRenameArgs,
        PoolDatasetRenameResult,
        audit='Pool dataset rename from',
        audit_extended=lambda id_, options: f'{id_!r} to {options["new_name"]!r}',
        roles=['DATASET_WRITE']
    )
    async def rename(self, id_, options):
        """
        Rename a ZFS resource (filesystem, snapshot, or zvolume) identified by ``id``.

        .. warning::

            No safety checks are performed when renaming ZFS resources. If the resource is in use by services
            such as SMB, iSCSI, snapshot tasks, replication, or cloud sync, renaming may cause disruptions or
            service failures. Proceed only if you are certain the resource is not in use and fully understand
            the risks; set ``force`` to continue.

        The ``recursive`` option is only valid for renaming snapshots. If ``true``, and a snapshot is given, the
        snapshot is renamed recursively for all children -- for example, ``dozer/a@now`` and ``dozer/a/b@now``
        are renamed to ``dozer/a@new`` and ``dozer/a/b@new``. Renaming snapshots is likewise not recommended.
        """
        if not options['force']:
            raise ValidationError(
                'pool.dataset.rename.force',
                'No safety checks are performed when renaming ZFS resources; this may break existing usages. '
                'If you understand the risks, please set force and proceed.'
            )
        if options['recursive']:
            raise ValidationError('pool.dataset.rename.recursive', 'recursive is only valid for snapshots')
        return await self.call2(
            self.s.zfs.resource.rename,
            ZFSResourceRenameArgsData(current_name=id_, new_name=options['new_name'], force=True),
        )
