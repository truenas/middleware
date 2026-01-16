import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (
    IscsiTargetToExtentEntry,
    iSCSITargetToExtentCreateArgs,
    iSCSITargetToExtentCreateResult,
    iSCSITargetToExtentUpdateArgs,
    iSCSITargetToExtentUpdateResult,
    iSCSITargetToExtentDeleteArgs,
    iSCSITargetToExtentDeleteResult)

from middlewared.service import CallError, CRUDService, ValidationErrors, private


class iSCSITargetToExtentModel(sa.Model):
    __tablename__ = 'services_iscsitargettoextent'
    __table_args__ = (
        sa.Index(
            'services_iscsitargettoextent_iscsi_target_id_757cc851_uniq',
            'iscsi_target_id', 'iscsi_extent_id', unique=True
        ),
    )

    id = sa.Column(sa.Integer(), primary_key=True)
    iscsi_extent_id = sa.Column(sa.ForeignKey('services_iscsitargetextent.id'), index=True)
    iscsi_target_id = sa.Column(sa.ForeignKey('services_iscsitarget.id'), index=True)
    iscsi_lunid = sa.Column(sa.Integer())


class iSCSITargetToExtentService(CRUDService):

    class Config:
        namespace = 'iscsi.targetextent'
        datastore = 'services.iscsitargettoextent'
        datastore_prefix = 'iscsi_'
        datastore_extend = 'iscsi.targetextent.extend'
        cli_namespace = 'sharing.iscsi.target.extent'
        role_prefix = 'SHARING_ISCSI_TARGETEXTENT'
        entry = IscsiTargetToExtentEntry

    @api_method(
        iSCSITargetToExtentCreateArgs,
        iSCSITargetToExtentCreateResult,
        audit='Create iSCSI target/LUN/extent mapping',
        audit_callback=True
    )
    async def do_create(self, audit_callback, data):
        """
        Create an Associated Target.

        `lunid` will be automatically assigned if it is not provided based on the `target`.
        """
        # It is unusual to do a audit_callback on a do_create, but we want to perform
        # more extensive operations than is usual for a create ... because the parameters
        # supplied as so opaque to the user.
        audit_callback(await self._mapping_summary(data))

        verrors = ValidationErrors()

        await self.validate(data, 'iscsi_targetextent_create', verrors)

        verrors.check()

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix}
        )

        await self._service_change('iscsitarget', 'reload', options={'ha_propagate': False})
        if await self.middleware.call("iscsi.global.alua_enabled") and await self.middleware.call('failover.remote_connected'):
            # If we have just added a new extent to an existing target, then STANDBY node may already be logged
            # into the target, so we should force a rescan.  Check the target LUN count.
            target_id = data['target']
            if await self.middleware.call('iscsi.targetextent.query',
                                          [['target', '=', target_id]],
                                          {'count': True}) > 1:
                target_name = (await self.middleware.call('iscsi.target.query',
                                                          [['id', '=', target_id]],
                                                          {'select': ['name'], 'get': True}))['name']
                try:
                    await self.middleware.call('failover.call_remote', 'iscsi.alua.added_target_extent', [target_name])
                except CallError as e:
                    if e.errno != CallError.ENOMETHOD:
                        self.logger.warning('Failed up update STANDBY node', exc_info=True)
                        # Better to continue than to raise the exception
            # Now update the remote node
            await self.middleware.call(
                'failover.call_remote', 'service.control', ['RELOAD', 'iscsitarget'], {'job': True},
            )
            await self.middleware.call('iscsi.alua.wait_cluster_mode', data['target'], data['extent'])
            await self.middleware.call('iscsi.alua.wait_for_alua_settled')

        return await self.get_instance(data['id'])

    def _set_null_false(name):
        def set_null_false(attr):
            attr.null = False
        return {'name': name, 'method': set_null_false}

    async def _mapping_summary(self, data):
        try:
            target = (await self.middleware.call('iscsi.target.query', [['id', '=', data.get('target')]], {'get': True}))['name']
        except Exception:
            target = data.get('target')

        try:
            extent = (await self.middleware.call('iscsi.extent.query', [['id', '=', data.get('extent')]], {'get': True}))['name']
        except Exception:
            extent = data.get('extent')

        return f'{target}/{data.get("lunid")}/{extent}'

    @api_method(
        iSCSITargetToExtentUpdateArgs,
        iSCSITargetToExtentUpdateResult,
        audit='Update iSCSI target/LUN/extent mapping',
        audit_callback=True
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update Associated Target of `id`.
        """
        verrors = ValidationErrors()
        old = await self.get_instance(id_)
        audit_callback(await self._mapping_summary(old))

        new = old.copy()
        new.update(data)

        await self.validate(new, 'iscsi_targetextent_update', verrors, old)

        verrors.check()

        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix})

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(id_)

    @api_method(
        iSCSITargetToExtentDeleteArgs,
        iSCSITargetToExtentDeleteResult,
        audit='Delete iSCSI target/LUN/extent mapping',
        audit_callback=True
    )
    async def do_delete(self, audit_callback, id_, force):
        """
        Delete Associated Target of `id`.
        """
        associated_target = await self.get_instance(id_)
        active_sessions = await self.middleware.call(
            'iscsi.target.active_sessions_for_targets', [associated_target['target']]
        )
        if active_sessions:
            if force:
                self.middleware.logger.warning('Associated target %s is in use.', active_sessions[0])
            else:
                raise CallError(f'Associated target {active_sessions[0]} is in use.')

        audit_callback(await self._mapping_summary(associated_target))
        result = await self.middleware.call(
            'datastore.delete', self._config.datastore, id_
        )

        # Reload the target, so that the LUN is removed from what is being offered ... including
        # on the internal target, if this is an ALUA system.
        await self._service_change('iscsitarget', 'reload', options={'ha_propagate': False})

        # Next, perform any necessary fixup on the STANDBY system if ALUA is enabled.
        if await self.middleware.call("iscsi.global.alua_enabled") and await self.middleware.call('failover.remote_connected'):
            target_name = (await self.middleware.call('iscsi.target.query',
                                                      [['id', '=', associated_target['target']]],
                                                      {'select': ['name'], 'get': True}))['name']
            extent_name = (await self.middleware.call('iscsi.extent.query',
                                                      [['id', '=', associated_target['extent']]],
                                                      {'select': ['name'], 'get': True}))['name']

            # Check that the HA target is no longer offering the LUN that we just deleted.  Wait a short period
            # if necessary (though this should not be required).
            await self.middleware.call(
                'iscsi.target.wait_for_ha_lun_absent',
                target_name,
                associated_target['lunid']
            )

            try:
                # iscsi.alua.removed_target_extent includes a local service reload
                await self.middleware.call(
                    'failover.call_remote',
                    'iscsi.alua.removed_target_extent',
                    [target_name, associated_target['lunid'], extent_name]
                )
            except CallError as e:
                if e.errno != CallError.ENOMETHOD:
                    self.logger.warning('Failed up update STANDBY node', exc_info=True)
                    # Better to continue than to raise the exception
                await self.middleware.call(
                    'failover.call_remote', 'service.control', ['RELOAD', 'iscsitarget'], {'job': True},
                )
            await self.middleware.call('iscsi.alua.wait_for_alua_settled')

        return result

    @private
    async def extend(self, data):
        data['target'] = data['target']['id']
        data['extent'] = data['extent']['id']

        return data

    @private
    async def validate(self, data, schema_name, verrors, old=None):
        if old is None:
            old = {}

        old_lunid = old.get('lunid')
        target = data['target']
        old_target = old.get('target')
        extent = data['extent']
        old_extent = old.get('extent')
        if data.get('lunid') is None:
            lunids = [
                o['lunid'] for o in await self.query(
                    [('target', '=', target)], {'order_by': ['lunid'], 'force_sql_filters': True}
                )
            ]
            if not lunids:
                lunid = 0
            else:
                diff = sorted(set(range(0, lunids[-1] + 1)).difference(lunids))
                lunid = diff[0] if diff else max(lunids) + 1

            data['lunid'] = lunid
        else:
            lunid = data['lunid']

        # For Linux we have
        # http://github.com/bvanassche/scst/blob/d483590da4de7d32c8371e0712fc186f3d8c509c/scst/include/scst_const.h#L69
        lun_map_size = 16383

        if lunid < 0 or lunid > lun_map_size - 1:
            verrors.add(
                f'{schema_name}.lunid',
                f'LUN ID must be a positive integer and lower than {lun_map_size - 1}'
            )

        # If either the LUN or the target name have changed then
        # ensure that we are not clashing with something pre-existing
        if (old_lunid != lunid or old_target != target) and await self.query([
            ('lunid', '=', lunid), ('target', '=', target)
        ], {'force_sql_filters': True}):
            verrors.add(
                f'{schema_name}.lunid',
                'LUN ID is already being used for this target.'
            )

        # Need to ensure that a particular extent is only ever used in
        # a single target (at a single LUN) at a time.  Failure to
        # do so would result in a mechanism to avoid any SCSI based
        # locking, and therefore could result in data corruption.
        if old_extent != extent and await self.query([
            ('extent', '=', extent)
        ], {'force_sql_filters': True}):
            verrors.add(
                f'{schema_name}.extent',
                'Extent is already in use.'
            )
