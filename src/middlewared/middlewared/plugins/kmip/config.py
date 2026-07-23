# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from truenas_crypto_utils.validation import validate_cert_with_chain

from middlewared.api.current import KMIPEntry, KMIPUpdate
from middlewared.async_validators import validate_port
from middlewared.service import CallError, ConfigServicePart, ValidationErrors
import middlewared.sqlalchemy as sa

from .connection import test_connection

if TYPE_CHECKING:
    from middlewared.job import Job


SYNC_ERROR = (
    'KMIP sync is pending, please make sure database and KMIP server '
    'are in sync before proceeding with this operation.'
)


class KMIPModel(sa.Model):
    __tablename__ = 'system_kmip'

    id = sa.Column(sa.Integer(), primary_key=True)
    server = sa.Column(sa.String(128), default=None, nullable=True)
    ssl_version = sa.Column(sa.String(128), default='PROTOCOL_TLSv1_2')
    port = sa.Column(sa.SmallInteger(), default=5696)
    certificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    certificate_authority_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    manage_sed_disks = sa.Column(sa.Boolean(), default=False)
    manage_zfs_keys = sa.Column(sa.Boolean(), default=False)
    enabled = sa.Column(sa.Boolean(), default=False)


class KMIPConfigServicePart(ConfigServicePart[KMIPEntry]):
    _datastore = 'system_kmip'
    _entry = KMIPEntry

    async def extend(self, data: dict[str, Any]) -> dict[str, Any]:
        for k in filter(lambda v: data[v], ('certificate', 'certificate_authority')):
            data[k] = data[k]['id']
        return data

    async def do_update(self, job: Job, data: KMIPUpdate) -> KMIPEntry:
        old = await self.config()
        update_dict = data.model_dump(exclude_unset=True)
        force_clear = update_dict.pop('force_clear', False)
        change_server = update_dict.pop('change_server', False)
        do_validate = update_dict.pop('validate', True)
        new = {**old.model_dump(), **update_dict}
        verrors = ValidationErrors()

        if not new['server'] and new['enabled']:
            verrors.add('kmip_update.server', 'Please specify a valid hostname or an IPv4 address')

        if new['enabled']:
            cert_id: int = new['certificate']
            sub_verrors = await self.call2(
                self.s.certificate.cert_services_validation, cert_id, 'kmip_update.certificate', False,
            )
            if sub_verrors:
                verrors.extend(sub_verrors)

        verrors.extend(await validate_port(self.middleware, 'kmip_update.port', new['port'], 'kmip'))

        ca_list = await self.call2(
            self.s.certificate.query,
            [['id', '=', new['certificate_authority']]],
        )
        if ca_list and not verrors:
            ca = ca_list[0]
            cert_entry = await self.call2(
                self.s.certificate.get_instance, new['certificate'],
            )
            cert_pem = cert_entry.certificate or ''
            ca_pem = ca.certificate or ''
            if not await self.to_thread(validate_cert_with_chain, cert_pem, [ca_pem]):
                verrors.add(
                    'kmip_update.certificate_authority',
                    'Certificate chain could not be verified with specified certificate authority.'
                )
        elif not ca_list and new['enabled']:
            verrors.add('kmip_update.certificate_authority', 'Please specify a valid id.')

        if do_validate and new['enabled'] and not verrors:
            if not await self.to_thread(test_connection, self, new):
                verrors.add('kmip_update.server', f'Unable to connect to {new["server"]}:{new["port"]} KMIP server.')

        clear_keys = force_clear if change_server else False
        if change_server and new['server'] == old.server:
            verrors.add('kmip_update.change_server', 'Please update server field to reflect the new server.')
        if change_server and not new['enabled']:
            verrors.add('kmip_update.enabled', 'Must be enabled when change server is enabled.')

        if old.enabled != new['enabled'] and await self.call2(self.s.kmip.kmip_sync_pending):
            if force_clear:
                clear_keys = True
            else:
                verrors.add('kmip_update.enabled', SYNC_ERROR)

        verrors.check()

        job.set_progress(30, 'Initial Validation complete')

        if clear_keys:
            await self.call2(self.s.kmip.clear_sync_pending_keys)
            job.set_progress(50, 'Cleared keys pending sync')

        if change_server:
            # We will first migrate all the keys to local database - once done with that,
            # we will proceed with pushing it to the new server - we should have the old server
            # old server -> db
            # db -> new server
            # First can be skipped if old server is not reachable and we want to clear keys
            job.set_progress(55, 'Starting migration from existing server to new server')
            await self.middleware.call(
                'datastore.update', self._datastore, old.id, {
                    'manage_zfs_keys': False, 'manage_sed_disks': False
                }
            )
            job.set_progress(60, 'Syncing keys from existing server to local database')
            sync_jobs = [
                await self.call2(self.s.kmip.sync_zfs_keys),
                await self.call2(self.s.kmip.sync_sed_keys),
            ]
            errors = []
            for sync_job in sync_jobs:
                await sync_job.wait()
                if sync_job.error:
                    errors.append(sync_job.error)
                elif sync_job.result:
                    errors.append(f'Failed to sync {",".join(sync_job.result)}')

            if errors:
                await self.middleware.call('datastore.update', self._datastore, old.id, old.model_dump())
                # We do this because it's possible a few datasets/disks got synced to db and few didn't - this is
                # to push all the data of interest back to the KMIP server from db
                await self.call2(self.s.kmip.sync_keys)
                error_str = '\n'.join(errors)
                raise CallError(f'Failed to sync keys from {old.server} to host: {error_str}')

            if await self.call2(self.s.kmip.kmip_sync_pending):
                raise CallError(SYNC_ERROR)

            job.set_progress(80, 'Successfully synced keys from existing server to local database')

        await self.middleware.call(
            'datastore.update', self._datastore, old.id, new,
        )

        if new['enabled']:
            await (await self.call2(self.s.service.control, 'START', 'kmip')).wait(raise_error=True)
        else:
            await self.middleware.call('etc.generate', 'kmip')

        if new['enabled'] and old.enabled != new['enabled']:
            await self.call2(self.s.kmip.initialize_keys)
        if any(getattr(old, k) != new[k] for k in ('enabled', 'manage_zfs_keys', 'manage_sed_disks')) or change_server:
            job.set_progress(90, 'Starting sync between local database and configured KMIP server')
            await self.call2(self.s.kmip.sync_keys)

        return await self.config()
