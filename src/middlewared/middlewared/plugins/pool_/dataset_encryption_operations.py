from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.service import CallError, ValidationErrors
from middlewared.utils import secrets

if TYPE_CHECKING:
    from middlewared.api.current import (
        PoolDatasetChangeKeyOptions,
        PoolDatasetInsertOrUpdateEncryptedRecordData,
    )
    from middlewared.job import Job
    from middlewared.service import ServiceContext

from .utils import DATASET_DATABASE_MODEL_NAME, ZFSKeyFormat


async def insert_or_update_encrypted_record(ctx: ServiceContext, data: PoolDatasetInsertOrUpdateEncryptedRecordData) -> int | None:
    # Convert BaseModel to dict for datastore operations
    data_dict = data.model_dump()

    key_format = data_dict.pop('key_format') or ZFSKeyFormat.PASSPHRASE.value
    if not data_dict['encryption_key'] or ZFSKeyFormat(key_format.upper()) == ZFSKeyFormat.PASSPHRASE:
        # We do not want to save passphrase keys - they are only known to the user
        return None

    ds_id = data_dict.pop('id')
    ds = await ctx.middleware.call(
        'datastore.query', DATASET_DATABASE_MODEL_NAME,
        [['id', '=', ds_id]] if ds_id else [['name', '=', data_dict['name']]]
    )

    pk = ds[0]['id'] if ds else None
    if ds:
        await ctx.middleware.call(
            'datastore.update',
            DATASET_DATABASE_MODEL_NAME,
            ds[0]['id'], data_dict
        )
    else:
        pk = await ctx.middleware.call(
            'datastore.insert',
            DATASET_DATABASE_MODEL_NAME,
            data_dict
        )

    kmip_config = await ctx.middleware.call('kmip.config')
    if kmip_config['enabled'] and kmip_config['manage_zfs_keys']:
        await ctx.middleware.call('kmip.sync_zfs_keys', [pk])

    return pk


async def delete_encrypted_datasets_from_db(ctx: ServiceContext, filters: list) -> None:
    datasets = await ctx.middleware.call('datastore.query', DATASET_DATABASE_MODEL_NAME, filters)
    for ds in datasets:
        if ds['kmip_uid']:
            ctx.middleware.create_task(ctx.middleware.call('kmip.reset_zfs_key', ds['name'], ds['kmip_uid']))
        await ctx.middleware.call('datastore.delete', DATASET_DATABASE_MODEL_NAME, ds['id'])


def validate_encryption_data(ctx: ServiceContext, job: Job | None, verrors: ValidationErrors, encryption_dict: dict, schema: str) -> dict:
    opts = {}
    if not encryption_dict['enabled']:
        return opts

    key = encryption_dict['key']
    passphrase = encryption_dict['passphrase']
    passphrase_key_format = bool(encryption_dict['passphrase'])

    if passphrase_key_format:
        for f in filter(lambda k: encryption_dict[k], ('key', 'key_file', 'generate_key')):
            verrors.add(f'{schema}.{f}', 'Must be disabled when dataset is to be encrypted with passphrase.')
    else:
        provided_opts = [k for k in ('key', 'key_file', 'generate_key') if encryption_dict[k]]
        if not provided_opts:
            verrors.add(
                f'{schema}.key',
                'Please provide a key or select generate_key to automatically generate '
                'a key when passphrase is not provided.'
            )
        elif len(provided_opts) > 1:
            for k in provided_opts:
                verrors.add(f'{schema}.{k}', f'Only one of {", ".join(provided_opts)} must be provided.')

    if not verrors:
        key = key or passphrase
        if encryption_dict['generate_key']:
            key = secrets.token_hex(32)
        elif not key and job:
            job.check_pipe('input')
            key = job.pipes.input.r.read(64)
            # We would like to ensure key matches specified key format
            try:
                key = hex(int(key, 16))[2:]
                if len(key) != 64:
                    raise ValueError('Invalid key')
            except ValueError:
                verrors.add(f'{schema}.key_file', 'Please specify a valid key')
                return {}

        opts = {
            'keyformat': (ZFSKeyFormat.PASSPHRASE if passphrase_key_format else ZFSKeyFormat.HEX).value.lower(),
            'keylocation': 'prompt',
            'encryption': encryption_dict['algorithm'].lower(),
            'key': key,
            **({'pbkdf2iters': encryption_dict['pbkdf2iters']} if passphrase_key_format else {}),
        }
    return opts


async def change_key_impl(ctx: ServiceContext, job: Job, id_: str, options: PoolDatasetChangeKeyOptions) -> None:
    ds = await ctx.call2(ctx.s.pool.dataset.get_instance_quick, id_, {'encryption': True})
    verrors = ValidationErrors()
    if not ds.encrypted:
        verrors.add('id', 'Dataset is not encrypted')
    elif ds.locked:
        verrors.add('id', 'Dataset must be unlocked before key can be changed')

    passphrase = getattr(options, 'passphrase', None)
    if not verrors:
        if passphrase:
            key = getattr(options, 'key', None)
            if options.generate_key or key:
                verrors.add(
                    'change_key_options.key',
                    f'Must not be specified when passphrase for {id_} is supplied.'
                )
            elif any(
                d['name'] == d['encryption_root']
                for d in await ctx.middleware.call(
                    'pool.dataset.query', [
                        ['id', '^', f'{id_}/'], ['encrypted', '=', True],
                        ['key_format.value', '!=', ZFSKeyFormat.PASSPHRASE.value]
                    ]
                )
            ):
                verrors.add(
                    'change_key_options.passphrase',
                    f'{id_} has children which are encrypted with a key. It is not allowed to have encrypted '
                    'roots which are encrypted with a key as children for passphrase encrypted datasets.'
                )
            elif id_ == (await ctx.middleware.call('systemdataset.config'))['pool']:
                verrors.add(
                    'id',
                    f'{id_} contains the system dataset. Please move the system dataset to a '
                    'different pool before changing key_format.'
                )
        else:
            key = getattr(options, 'key', None)
            if not options.generate_key and not key:
                for k in ('key', 'passphrase', 'generate_key'):
                    verrors.add(
                        f'change_key_options.{k}',
                        'Either Key or passphrase must be provided.'
                    )
            elif id_.count('/') and await ctx.middleware.call(
                    'pool.dataset.query', [
                        ['id', 'in', [id_.rsplit('/', i)[0] for i in range(1, id_.count('/') + 1)]],
                        ['key_format.value', '=', ZFSKeyFormat.PASSPHRASE.value], ['encrypted', '=', True]
                    ]
            ):
                verrors.add(
                    'change_key_options.key',
                    f'{id_} has parent(s) which are encrypted with a passphrase. It is not allowed to have '
                    'encrypted roots which are encrypted with a key as children for passphrase encrypted datasets.'
                )

    verrors.check()

    encryption_dict = await ctx.middleware.call(
        'pool.dataset.validate_encryption_data', job, verrors, {
            'enabled': True, 'passphrase': passphrase,
            'generate_key': options.generate_key, 'key_file': options.key_file,
            'pbkdf2iters': options.pbkdf2iters, 'algorithm': 'on', 'key': getattr(options, 'key', None),
        }, 'change_key_options'
    )

    verrors.check()

    encryption_dict.pop('encryption')
    key = encryption_dict.pop('key')

    await ctx.middleware.call(
        'zfs.dataset.change_key', id_, {
            'encryption_properties': encryption_dict,
            'key': key, 'load_key': False,
        }
    )

    # TODO: Handle renames of datasets appropriately wrt encryption roots and db
    data = {'encryption_key': key, 'key_format': 'PASSPHRASE' if passphrase else 'HEX', 'name': id_}
    await ctx.call2(ctx.s.pool.dataset.insert_or_update_encrypted_record, data)
    if passphrase and ZFSKeyFormat(ds.key_format.value) != ZFSKeyFormat.PASSPHRASE:
        await ctx.middleware.call('pool.dataset.sync_db_keys', id_)

    data['old_key_format'] = ds.key_format.value
    await ctx.middleware.call_hook('dataset.change_key', data)


async def inherit_parent_encryption_properties_impl(ctx: ServiceContext, id_: str) -> None:
    ds = await ctx.call2(ctx.s.pool.dataset.get_instance_quick, id_, {'encryption': True})
    if not ds.encrypted:
        raise CallError(f'Dataset {id_} is not encrypted')
    elif ds.encryption_root != id_:
        raise CallError(f'Dataset {id_} is not an encryption root')
    elif ds.locked:
        raise CallError('Dataset must be unlocked to perform this operation')
    elif '/' not in id_:
        raise CallError('Root datasets do not have a parent and cannot inherit encryption settings')
    else:
        parent = await ctx.call2(
            ctx.s.pool.dataset.get_instance_quick, id_.rsplit('/', 1)[0], {'encryption': True}
        )
        if not parent.encrypted:
            raise CallError('This operation requires the parent dataset to be encrypted')
        else:
            parent_encrypted_root = await ctx.call2(
                ctx.s.pool.dataset.get_instance_quick, parent.encryption_root, {'encryption': True}
            )
            if ZFSKeyFormat(parent_encrypted_root.key_format.value) == ZFSKeyFormat.PASSPHRASE.value:
                if any(
                    d['name'] == d['encryption_root']
                    for d in await ctx.middleware.call(
                        'pool.dataset.query', [
                            ['id', '^', f'{id_}/'], ['encrypted', '=', True],
                            ['key_format.value', '!=', ZFSKeyFormat.PASSPHRASE.value]
                        ]
                    )
                ):
                    raise CallError(
                        f'{id_} has children which are encrypted with a key. It is not allowed to have encrypted '
                        'roots which are encrypted with a key as children for passphrase encrypted datasets.'
                    )

    await ctx.middleware.call('zfs.dataset.change_encryption_root', id_, {'load_key': False})
    await ctx.middleware.call('pool.dataset.sync_db_keys', id_)
    await ctx.middleware.call_hook('dataset.inherit_parent_encryption_root', id_)
