from middlewared.api import api_method
from middlewared.api.current import (
    PoolDatasetInsertOrUpdateEncryptedRecordArgs, PoolDatasetInsertOrUpdateEncryptedRecordResult,
    PoolDatasetChangeKeyArgs, PoolDatasetChangeKeyResult, PoolDatasetInheritParentEncryptionPropertiesArgs,
    PoolDatasetInheritParentEncryptionPropertiesResult
)
from middlewared.service import CallError, job, private, Service, ValidationErrors
from middlewared.utils import secrets

from .utils import DATASET_DATABASE_MODEL_NAME, ZFSKeyFormat


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @private
    @api_method(
        PoolDatasetInsertOrUpdateEncryptedRecordArgs,
        PoolDatasetInsertOrUpdateEncryptedRecordResult,
        roles=['DATASET_WRITE']
    )
    async def insert_or_update_encrypted_record(self, data):
        key_format = data.pop('key_format') or ZFSKeyFormat.PASSPHRASE.value
        if not data['encryption_key'] or ZFSKeyFormat(key_format.upper()) == ZFSKeyFormat.PASSPHRASE:
            # We do not want to save passphrase keys - they are only known to the user
            return

        ds_id = data.pop('id')
        ds = await self.middleware.call(
            'datastore.query', DATASET_DATABASE_MODEL_NAME,
            [['id', '=', ds_id]] if ds_id else [['name', '=', data['name']]]
        )

        data['encryption_key'] = data['encryption_key']

        pk = ds[0]['id'] if ds else None
        if ds:
            await self.middleware.call(
                'datastore.update',
                DATASET_DATABASE_MODEL_NAME,
                ds[0]['id'], data
            )
        else:
            pk = await self.middleware.call(
                'datastore.insert',
                DATASET_DATABASE_MODEL_NAME,
                data
            )

        kmip_config = await self.middleware.call('kmip.config')
        if kmip_config['enabled'] and kmip_config['manage_zfs_keys']:
            await self.middleware.call('kmip.sync_zfs_keys', [pk])

        return pk

    @private
    async def delete_encrypted_datasets_from_db(self, filters):
        datasets = await self.middleware.call('datastore.query', DATASET_DATABASE_MODEL_NAME, filters)
        for ds in datasets:
            if ds['kmip_uid']:
                self.middleware.create_task(self.middleware.call('kmip.reset_zfs_key', ds['name'], ds['kmip_uid']))
            await self.middleware.call('datastore.delete', DATASET_DATABASE_MODEL_NAME, ds['id'])

    @private
    def validate_encryption_data(self, job, verrors, encryption_dict, schema):
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

    @api_method(PoolDatasetChangeKeyArgs, PoolDatasetChangeKeyResult, roles=['DATASET_WRITE'])
    @job(lock=lambda args: f'dataset_change_key_{args[0]}', pipes=['input'], check_pipes=False)
    async def change_key(self, job, id_, options):
        """
        Change encryption properties for `id` encrypted dataset.

        Changing dataset encryption to use passphrase instead of a key is not allowed if:

        1) It has encrypted roots as children which are encrypted with a key
        2) If it is a root dataset where the system dataset is located
        """
        ds = await self.middleware.call('pool.dataset.get_instance_quick', id_, {
            'encryption': True,
        })
        verrors = ValidationErrors()
        if not ds['encrypted']:
            verrors.add('id', 'Dataset is not encrypted')
        elif ds['locked']:
            verrors.add('id', 'Dataset must be unlocked before key can be changed')

        if not verrors:
            if options['passphrase']:
                if options['generate_key'] or options['key']:
                    verrors.add(
                        'change_key_options.key',
                        f'Must not be specified when passphrase for {id_} is supplied.'
                    )
                elif any(
                    d['name'] == d['encryption_root']
                    for d in await self.middleware.call(
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
                elif id_ == (await self.middleware.call('systemdataset.config'))['pool']:
                    verrors.add(
                        'id',
                        f'{id_} contains the system dataset. Please move the system dataset to a '
                        'different pool before changing key_format.'
                    )
            else:
                if not options['generate_key'] and not options['key']:
                    for k in ('key', 'passphrase', 'generate_key'):
                        verrors.add(
                            f'change_key_options.{k}',
                            'Either Key or passphrase must be provided.'
                        )
                elif id_.count('/') and await self.middleware.call(
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

        encryption_dict = await self.middleware.call(
            'pool.dataset.validate_encryption_data', job, verrors, {
                'enabled': True, 'passphrase': options['passphrase'],
                'generate_key': options['generate_key'], 'key_file': options['key_file'],
                'pbkdf2iters': options['pbkdf2iters'], 'algorithm': 'on', 'key': options['key'],
            }, 'change_key_options'
        )

        verrors.check()

        encryption_dict.pop('encryption')
        key = encryption_dict.pop('key')

        await self.middleware.call(
            'zfs.dataset.change_key', id_, {
                'encryption_properties': encryption_dict,
                'key': key, 'load_key': False,
            }
        )

        # TODO: Handle renames of datasets appropriately wrt encryption roots and db - this will be done when
        #  devd changes are in from the OS end
        data = {'encryption_key': key, 'key_format': 'PASSPHRASE' if options['passphrase'] else 'HEX', 'name': id_}
        await self.insert_or_update_encrypted_record(data)
        if options['passphrase'] and ZFSKeyFormat(ds['key_format']['value']) != ZFSKeyFormat.PASSPHRASE:
            await self.middleware.call('pool.dataset.sync_db_keys', id_)

        data['old_key_format'] = ds['key_format']['value']
        await self.middleware.call_hook('dataset.change_key', data)

    @api_method(
        PoolDatasetInheritParentEncryptionPropertiesArgs,
        PoolDatasetInheritParentEncryptionPropertiesResult,
        roles=['DATASET_WRITE']
    )
    async def inherit_parent_encryption_properties(self, id_):
        """
        Allows inheriting parent's encryption root discarding its current encryption settings. This
        can only be done where `id` has an encrypted parent and `id` itself is an encryption root.
        """
        ds = await self.middleware.call('pool.dataset.get_instance_quick', id_, {
            'encryption': True,
        })
        if not ds['encrypted']:
            raise CallError(f'Dataset {id_} is not encrypted')
        elif ds['encryption_root'] != id_:
            raise CallError(f'Dataset {id_} is not an encryption root')
        elif ds['locked']:
            raise CallError('Dataset must be unlocked to perform this operation')
        elif '/' not in id_:
            raise CallError('Root datasets do not have a parent and cannot inherit encryption settings')
        else:
            parent = await self.middleware.call(
                'pool.dataset.get_instance_quick', id_.rsplit('/', 1)[0], {
                    'encryption': True,
                }
            )
            if not parent['encrypted']:
                raise CallError('This operation requires the parent dataset to be encrypted')
            else:
                parent_encrypted_root = await self.middleware.call(
                    'pool.dataset.get_instance_quick', parent['encryption_root'], {
                        'encryption': True,
                    }
                )
                if ZFSKeyFormat(parent_encrypted_root['key_format']['value']) == ZFSKeyFormat.PASSPHRASE.value:
                    if any(
                        d['name'] == d['encryption_root']
                        for d in await self.middleware.call(
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

        await self.middleware.call('zfs.dataset.change_encryption_root', id_, {'load_key': False})
        await self.middleware.call('pool.dataset.sync_db_keys', id_)
        await self.middleware.call_hook('dataset.inherit_parent_encryption_root', id_)
