from datetime import time

from middlewared.schema import accepts, Bool, Cron, Dict, Int, Patch, Str
from middlewared.service import CRUDService, private, ValidationErrors
from middlewared.validators import Time


class PeriodicSnapshotService(CRUDService):

    class Config:
        datastore = 'storage.task'
        datastore_prefix = 'task_'
        datastore_extend = 'pool.snapshot.periodic_snapshot_extend'
        namespace = 'pool.snapshot'

    @private
    def periodic_snapshot_extend(self, data):
        data['begin'] = str(data['begin'])
        data['end'] = str(data['end'])
        data['repeat_unit'] = data['repeat_unit'].upper()
        data['ret_unit'] = data['ret_unit'].upper()
        data['schedule'] = data.pop('byweekday')
        return data

    @private
    async def common_validation(self, data, schema_name):
        verrors = ValidationErrors()

        interval_choices = [5, 10, 15, 30, 60, 120, 180, 240, 360, 720, 1440, 10080, 20160, 40320]

        if data.get('interval') not in interval_choices:
            verrors.add(
                f'{schema_name}.interval',
                'Please select a valid interval'
            )

        if data['repeat_unit'] == 'WEEKLY' and not data['schedule'].get('dow'):
            verrors.add(
                f'{schema_name}.dow',
                'At least one day must be chosen'
            )

        data['repeat_unit'] = data['repeat_unit'].lower()
        data['ret_unit'] = data['ret_unit'].lower()
        data['begin'] = time(*[int(value) for value in data['begin'].split(':')])
        data['end'] = time(*[int(value) for value in data['end'].split(':')])
        data['byweekday'] = data.pop('schedule').get('dow')

        return data, verrors

    @accepts(
        Dict(
            'periodic_snapshot_create',
            Bool('enabled', default=True),
            Bool('recursive', default=False),
            Cron('schedule'),
            Int('interval', required=True),
            Int('ret_count', required=True),
            Str('begin', validators=[Time()], required=True),
            Str('end', validators=[Time()], required=True),
            Str('filesystem', required=True),
            Str('repeat_unit', enum=['DAILY', 'WEEKLY'], required=True),
            Str('ret_unit', enum=['HOUR', 'DAY', 'WEEK', 'MONTH', 'YEAR'], required=True),
            register=True
        )
    )
    async def do_create(self, data):

        data, verrors = await self.common_validation(data, 'periodic_snapshot_create')

        if data['filesystem'] not in (await self.middleware.call('pool.filesystem_choices')):
            verrors.add(
                'periodic_snapshot_create.filesystem',
                'Invalid ZFS filesystem'
            )

        if verrors:
            raise verrors

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call(
            'service.restart',
            'cron',
            {'onetime': False}
        )

        return await self._get_instance(data['id'])

    @accepts(
        Int('id', required=True),
        Patch('periodic_snapshot_create', 'periodic_snapshot_update', ('attr', {'update': True}))
    )
    async def do_update(self, id, data):

        old = await self._get_instance(id)
        new = old.copy()
        new.update(data)

        new, verrors = await self.common_validation(new, 'periodic_snapshot_update')
        if verrors:
            raise verrors

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call(
            'service.restart',
            'cron',
            {'onetime': False}
        )

        return await self._get_instance(id)

    @accepts(
        Int('id')
    )
    async def do_delete(self, id):
        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

        return response
