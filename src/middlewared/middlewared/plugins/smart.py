from itertools import chain

from middlewared.schema import accepts, Cron, Dict, Int, List, Patch, Str
from middlewared.validators import Email, Range, Unique
from middlewared.service import CRUDService, private, SystemServiceService, ValidationErrors


class SMARTTestService(CRUDService):

    class Config:
        datastore = 'tasks.smarttest'
        datastore_extend = 'smart.test.smart_test_extend'
        datastore_prefix = 'smarttest_'
        namespace = 'smart.test'

    async def smart_test_extend(self, data):
        disks = data.pop('disks')
        data['disks'] = [disk['disk_identifier'] for disk in disks]
        test_type = {
            'L': 'LONG',
            'S': 'SHORT',
            'C': 'CONVEYANCE',
            'O': 'OFFLINE',
        }
        data['type'] = test_type[data.pop('type')]
        Cron.convert_db_format_to_schedule(data)
        return data

    @private
    async def validate_data(self, data, schema):
        verrors = ValidationErrors()

        smart_tests = await self.query(filters=[('type', '=', data['type'])])
        configured_disks = [d for test in smart_tests for d in test['disks']]
        disks_dict = {disk['identifier']: disk['name'] for disk in (await self.middleware.call('disk.query'))}

        disks = data.get('disks')
        used_disks = []
        invalid_disks = []
        for disk in disks:
            if disk in configured_disks:
                used_disks.append(disks_dict[disk])
            if disk not in disks_dict.keys():
                invalid_disks.append(disk)

        if used_disks:
            verrors.add(
                f'{schema}.disks',
                f'The following disks already have tests for this type: {", ".join(used_disks)}'
            )

        if invalid_disks:
            verrors.add(
                f'{schema}.disks',
                f'The following disks are invalid: {", ".join(invalid_disks)}'
            )

        return verrors

    @accepts(
        Dict(
            'smart_task_create',
            Cron('schedule'),
            Str('desc'),
            List('disks', items=[Str('disk')], default=[], required=True),
            Str('type', enum=['LONG', 'SHORT', 'CONVEYANCE', 'OFFLINE'], required=True),
            register=True
        )
    )
    async def do_create(self, data):
        data['type'] = data.pop('type')[0]
        verrors = await self.validate_data(data, 'smart_test_create')

        if not data.get('disks'):
            verrors.add(
                'smart_test_create.disks',
                'This field is required'
            )

        if verrors:
            raise verrors

        Cron.convert_schedule_to_db_format(data)

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await self._service_change('smartd', 'restart')

        return data

    @accepts(
        Int('id', validators=[Range(min=1)]),
        Patch('smart_task_create', 'smart_task_update', ('attr', {'update': True}))
    )
    async def do_update(self, id, data):
        old = await self.query(filters=[('id', '=', id)], options={'get': True})
        new = old.copy()
        new.update(data)

        new['type'] = new.pop('type')[0]
        old['type'] = old.pop('type')[0]
        new_disks = [disk for disk in new['disks'] if disk not in old['disks']]
        deleted_disks = [disk for disk in old['disks'] if disk not in new['disks']]
        if old['type'] == new['type']:
            new['disks'] = new_disks
        verrors = await self.validate_data(new, 'smart_test_update')

        new['disks'] = [disk for disk in chain(new_disks, old['disks']) if disk not in deleted_disks]

        if not new.get('disks'):
            verrors.add(
                'smart_test_update.disks',
                'This field is required'
            )

        if verrors:
            raise verrors

        Cron.convert_schedule_to_db_format(new)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        await self._service_change('smartd', 'restart')

        return await self.query(filters=[('id', '=', id)], options={'get': True})

    @accepts(
        Int('id')
    )
    async def do_delete(self, id):
        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

        await self._service_change('smartd', 'restart')

        return response


class SmartService(SystemServiceService):

    class Config:
        service = "smartd"
        service_model = "smart"
        datastore_extend = "smart.smart_extend"
        datastore_prefix = "smart_"

    @private
    async def smart_extend(self, smart):
        smart["powermode"] = smart["powermode"].upper()
        smart["email"] = smart["email"].split(",")
        return smart

    @accepts(Dict(
        'smart_update',
        Int('interval'),
        Str('powermode', enum=['NEVER', 'SLEEP', 'STANDBY', 'IDLE']),
        Int('difference'),
        Int('informational'),
        Int('critical'),
        List('email', validators=[Unique()], items=[Str('email', validators=[Email()])]),
        update=True
    ))
    async def do_update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        new["powermode"] = new["powermode"].lower()
        new["email"] = ",".join([email.strip() for email in new["email"]])

        await self._update_service(old, new)

        await self.smart_extend(new)

        return new
