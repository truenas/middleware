from middlewared.schema import accepts, Bool, Cron, Dict, Int, Patch, Str
from middlewared.service import CRUDService, private, ValidationErrors
from middlewared.validators import Range


class CronJobService(CRUDService):

    class Config:
        datastore = 'tasks.cronjob'
        datastore_prefix = 'cron_'
        datastore_extend = 'cronjob.cron_extend'
        namespace = 'cronjob'

    @private
    def cron_extend(self, data):
        Cron.convert_db_format_to_schedule(data)
        return data

    @private
    async def validate_data(self, data, schema):
        verrors = ValidationErrors()

        user = data.get('user')
        if user:
            # Windows users can have spaces in their usernames
            # http://www.freebsd.org/cgi/query-pr.cgi?pr=164808
            if ' ' in user:
                verrors.add(
                    f'{schema}.user',
                    'Usernames cannot have spaces'
                )

            elif not (
                await self.middleware.call(
                    'notifier.get_user_object',
                    user
                )
            ):
                verrors.add(
                    f'{schema}.user',
                    'Specified user does not exist'
                )

        return verrors, data

    @accepts(
        Dict(
            'cron_job_create',
            Bool('enabled'),
            Bool('stderr'),
            Bool('stdout'),
            Cron('schedule'),
            Str('command', required=True),
            Str('description'),
            Str('user', required=True),
            register=True
        )
    )
    async def do_create(self, data):
        """
        Create a new cron job.

        `stderr` and `stdout` are boolean values which if `true`, represent that we would like to suppress
        standard error / standard output respectively.

        .. examples(websocket)::

          Create a cron job which executes `touch /tmp/testfile` after every 5 minutes.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "cronjob.create",
                "params": [{
                    "enabled": true,
                    "schedule": {
                        "minute": "5",
                        "hour": "*",
                        "dom": "*",
                        "month": "*",
                        "dow": "*"
                    },
                    "command": "touch /tmp/testfile",
                    "description": "Test command",
                    "user": "root",
                    "stderr": true,
                    "stdout": true
                }]
            }
        """
        verrors, data = await self.validate_data(data, 'cron_job_create')
        if verrors:
            raise verrors

        Cron.convert_schedule_to_db_format(data)

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await self.middleware.call('service.restart', 'cron')

        return data

    @accepts(
        Int('id', validators=[Range(min=1)]),
        Patch('cron_job_create', 'cron_job_update', ('attr', {'update': True}))
    )
    async def do_update(self, id, data):
        """
        Update cronjob of `id`.
        """
        task_data = await self.query(filters=[('id', '=', id)], options={'get': True})
        original_data = task_data.copy()
        task_data.update(data)
        verrors, task_data = await self.validate_data(task_data, 'cron_job_update')

        if verrors:
            raise verrors

        Cron.convert_schedule_to_db_format(task_data)
        Cron.convert_schedule_to_db_format(original_data)

        if len(set(task_data.items()) ^ set(original_data.items())) > 0:

            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                id,
                task_data,
                {'prefix': self._config.datastore_prefix}
            )

            await self.middleware.call('service.restart', 'cron')

        return await self.query(filters=[('id', '=', id)], options={'get': True})

    @accepts(
        Int('id')
    )
    async def do_delete(self, id):
        """
        Delete cronjob of `id`.
        """
        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

        await self.middleware.call('service.restart', 'cron')

        return response
