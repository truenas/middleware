from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.service_exception import MatchNotFound

from .extents import iSCSITargetExtentService


class ISCSIFSAttachmentDelegate(LockableFSAttachmentDelegate):
    name = 'iscsi'
    title = 'iSCSI Extent'
    service = 'iscsitarget'
    service_class = iSCSITargetExtentService

    async def get_query_filters(self, enabled, options=None):
        return [['type', '=', 'DISK']] + (await super().get_query_filters(enabled, options))

    async def delete(self, attachments):
        orphan_targets_ids = set()
        for attachment in attachments:
            for te in await self.middleware.call('iscsi.targetextent.query', [['extent', '=', attachment['id']]]):
                orphan_targets_ids.add(te['target'])
                await self.middleware.call('datastore.delete', 'services.iscsitargettoextent', te['id'])

            await self.middleware.call('datastore.delete', 'services.iscsitargetextent', attachment['id'])
            await self.remove_alert(attachment)

        for te in await self.middleware.call('iscsi.targetextent.query', [['target', 'in', orphan_targets_ids]]):
            orphan_targets_ids.discard(te['target'])
        for target_id in orphan_targets_ids:
            await self.middleware.call('iscsi.target.delete', target_id, True)

        await self._service_change('iscsitarget', 'reload')

    async def restart_reload_services(self, attachments):
        await self._service_change('iscsitarget', 'reload')

    async def stop(self, attachments):
        if attachments:
            # Reload ACTIVE
            await self._service_change(
                'iscsitarget',
                'reload',
                options={'ha_propagate': False}
            )
            alua_enabled = await self.middleware.call('iscsi.global.alua_enabled')
            if alua_enabled and await self.middleware.call('failover.remote_connected'):
                for extent in attachments:
                    try:
                        assoc = await self.middleware.call(
                            'iscsi.targetextent.query',
                            [['extent', '=', extent['id']]],
                            {'get': True}
                        )
                        target_name = (await self.middleware.call(
                            'iscsi.target.query',
                            [['id', '=', assoc['target']]],
                            {'select': ['name'], 'get': True}))['name']
                    except MatchNotFound:
                        self.logger.debug(
                            'Failed to obtain details for extent %r (%r)',
                            extent['id'],
                            extent['name']
                        )
                        continue

                    # Check that the HA target is no longer offering the LUN that we just deleted.
                    # Wait a short period if necessary (though this should not be required).
                    await self.middleware.call(
                        'iscsi.target.wait_for_ha_lun_absent',
                        target_name,
                        assoc['lunid']
                    )
                    try:
                        # iscsi.alua.removed_target_extent includes a local service reload
                        # Turn off the implicit RELOAD as we'll reload when finished the
                        # attachments loop.
                        await self.middleware.call(
                            'failover.call_remote',
                            'iscsi.alua.removed_target_extent',
                            [target_name, assoc['lunid'], extent['name'], False]
                        )
                    except Exception:
                        self.logger.warning('Failed up update STANDBY node', exc_info=True)
                        # Better to continue than to raise the exception
                # Now that all extents have been processed, reload STANDBY
                await self.middleware.call(
                    'failover.call_remote',
                    'service.control',
                    ['RELOAD', 'iscsitarget'],
                    {'job': True},
                )
                await self.middleware.call('iscsi.alua.wait_for_alua_settled')

    async def start(self, attachments):
        if attachments:
            alua_enabled = await self.middleware.call('iscsi.global.alua_enabled')
            remote_connected = await self.middleware.call('failover.remote_connected')
            service_started = await self.middleware.call('service.started', self.service)
            if alua_enabled and remote_connected and service_started:
                await self._service_change(
                    'iscsitarget',
                    'reload',
                    options={'ha_propagate': False}
                )
                for extent in attachments:
                    try:
                        assoc = await self.middleware.call(
                            'iscsi.targetextent.query',
                            [['extent', '=', extent['id']]],
                            {'get': True}
                        )
                        target_name = (await self.middleware.call(
                            'iscsi.target.query',
                            [['id', '=', assoc['target']]],
                            {'select': ['name'], 'get': True}))['name']
                    except MatchNotFound:
                        self.logger.warning('Failed up update extent %r %r',
                                            extent['id'], extent['name'])
                        continue
                    await self.middleware.call(
                        'iscsi.target.wait_for_ha_lun_present',
                        target_name,
                        assoc['lunid']
                    )
                    try:
                        await self.middleware.call(
                            'failover.call_remote',
                            'iscsi.alua.added_target_extent',
                            [target_name]
                        )
                    except Exception:
                        self.logger.warning(
                            'Failed up update STANDBY node for %r %r',
                            extent['id'], extent['name'],
                            exc_info=True
                        )
                        # Better to continue than to raise the exception
                # Now update the remote node
                await self.middleware.call(
                    'failover.call_remote',
                    'service.control',
                    ['RELOAD', 'iscsitarget'],
                    {'job': True},
                )
                await self.middleware.call(
                    'iscsi.alua.wait_cluster_mode',
                    assoc['target'],
                    assoc['extent']
                )
            else:
                await super().start(attachments)


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', ISCSIFSAttachmentDelegate(middleware))
