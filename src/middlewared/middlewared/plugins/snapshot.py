from datetime import time

from middlewared.schema import accepts, Bool, Dict, Int, List, Patch, Str
from middlewared.service import CRUDService, private, ValidationErrors
from middlewared.validators import Range, Time


class PeriodicSnapshotTaskService(CRUDService):

    class Config:
        datastore = 'storage.task'
        datastore_prefix = 'task_'
        datastore_extend = 'pool.snapshottask.periodic_snapshot_extend'
        namespace = 'pool.snapshottask'

    @private
    def periodic_snapshot_extend(self, data):
        data['begin'] = str(data['begin'])
        data['end'] = str(data['end'])
        data['ret_unit'] = data['ret_unit'].upper()
        data['dow'] = [int(day) for day in data.pop('byweekday').split(',')]
        data.pop('repeat_unit', None)
        return data

    @private
    async def common_validation(self, data, schema_name):
        verrors = ValidationErrors()

        if not data['dow']:
            verrors.add(
                f'{schema_name}.dow',
                'At least one day must be chosen'
            )

        data['ret_unit'] = data['ret_unit'].lower()
        data['begin'] = time(*[int(value) for value in data['begin'].split(':')])
        data['end'] = time(*[int(value) for value in data['end'].split(':')])
        data['byweekday'] = ','.join([str(day) for day in data.pop('dow')])

        return data, verrors

    @accepts(
        Dict(
            'periodic_snapshot_create',
            Bool('enabled', default=True),
            Bool('recursive', default=False),
            Int('interval', enum=[
                5, 10, 15, 30, 60, 120, 180, 240,
                360, 720, 1440, 10080, 20160, 40320
            ], required=True),
            Int('ret_count', required=True),
            List('dow', items=[
                Int('day', validators=[Range(min=1, max=7)])
            ], required=True),
            Str('begin', validators=[Time()], required=True),
            Str('end', validators=[Time()], required=True),
            Str('filesystem', required=True),
            Str('ret_unit', enum=[
                'HOUR', 'DAY', 'WEEK', 'MONTH', 'YEAR'
            ], required=True),
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

        await self.middleware.call('service.restart', 'cron')

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

        if old['filesystem'] != new['filesystem']:
            if new['filesystem'] not in (await self.middleware.call('pool.filesystem_choices')):
                verrors.add(
                    'periodic_snapshot_update.filesystem',
                    'Invalid ZFS filesystem'
                )

        if verrors:
            raise verrors

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('service.restart', 'cron')

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

        await self.middleware.call('service.restart', 'cron')

        return response
