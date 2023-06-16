import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Bool, Dict, Int, Patch
from middlewared.service import CallError, CRUDService, private, ValidationErrors


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

    @accepts(Dict(
        'iscsi_targetextent_create',
        Int('target', required=True),
        Int('lunid', null=True),
        Int('extent', required=True),
        register=True
    ))
    async def do_create(self, data):
        """
        Create an Associated Target.

        `lunid` will be automatically assigned if it is not provided based on the `target`.
        """
        verrors = ValidationErrors()

        await self.validate(data, 'iscsi_targetextent_create', verrors)

        if verrors:
            raise verrors

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix}
        )

        await self._service_change('iscsitarget', 'reload')
        if await self.middleware.call("iscsi.global.alua_enabled") and await self.middleware.call('failover.remote_connected'):
            await self.middleware.call('failover.call_remote', 'service.reload', ['iscsitarget'])

        return await self.get_instance(data['id'])

    def _set_null_false(name):
        def set_null_false(attr):
            attr.null = False
        return {'name': name, 'method': set_null_false}

    @accepts(
        Int('id'),
        Patch(
            'iscsi_targetextent_create',
            'iscsi_targetextent_update',
            ('edit', _set_null_false('lunid')),
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id, data):
        """
        Update Associated Target of `id`.
        """
        verrors = ValidationErrors()
        old = await self.get_instance(id)

        new = old.copy()
        new.update(data)

        await self.validate(new, 'iscsi_targetextent_update', verrors, old)

        if verrors:
            raise verrors

        await self.middleware.call(
            'datastore.update', self._config.datastore, id, new,
            {'prefix': self._config.datastore_prefix})

        await self._service_change('iscsitarget', 'reload')

        return await self.get_instance(id)

    @accepts(Int('id'), Bool('force', default=False))
    async def do_delete(self, id, force):
        """
        Delete Associated Target of `id`.
        """
        associated_target = await self.get_instance(id)
        active_sessions = await self.middleware.call(
            'iscsi.target.active_sessions_for_targets', [associated_target['target']]
        )
        if active_sessions:
            if force:
                self.middleware.logger.warning('Associated target %s is in use.', active_sessions[0])
            else:
                raise CallError(f'Associated target {active_sessions[0]} is in use.')

        result = await self.middleware.call(
            'datastore.delete', self._config.datastore, id
        )

        await self._service_change('iscsitarget', 'reload')

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
