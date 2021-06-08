import contextlib
import errno

from middlewared.schema import accepts, Bool, Cron, Dict, Int, Patch, returns, Str
from middlewared.service import CallError, CRUDService, job, private, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.validators import Range
from middlewared.utils.osc import run_command_with_user_context

import syslog


class CronJobModel(sa.Model):
    __tablename__ = 'tasks_cronjob'

    id = sa.Column(sa.Integer(), primary_key=True)
    cron_minute = sa.Column(sa.String(100), default="00")
    cron_hour = sa.Column(sa.String(100), default="*")
    cron_daymonth = sa.Column(sa.String(100), default="*")
    cron_month = sa.Column(sa.String(100), default='*')
    cron_dayweek = sa.Column(sa.String(100), default="*")
    cron_user = sa.Column(sa.String(60))
    cron_command = sa.Column(sa.Text())
    cron_description = sa.Column(sa.String(200))
    cron_enabled = sa.Column(sa.Boolean(), default=True)
    cron_stdout = sa.Column(sa.Boolean(), default=True)
    cron_stderr = sa.Column(sa.Boolean(), default=False)


class CronJobService(CRUDService):

    class Config:
        datastore = 'tasks.cronjob'
        datastore_prefix = 'cron_'
        datastore_extend = 'cronjob.cron_extend'
        namespace = 'cronjob'
        cli_namespace = 'task.cron_job'

    ENTRY = Patch(
        'cron_job_create', 'cron_job_entry',
        ('add', Int('id')),
    )

    @private
    def cron_extend(self, data):
        Cron.convert_db_format_to_schedule(data)
        return data

    @private
    async def construct_cron_command(self, schedule, user, command, stdout=True, stderr=True):
        return list(
            filter(
                bool, (
                    schedule['minute'], schedule['hour'], schedule['dom'], schedule['month'],
                    schedule['dow'], user,
                    'PATH="/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:/root/bin"',
                    command.replace('\n', ''),
                    '> /dev/null' if stdout else '', '2> /dev/null' if stderr else ''
                )
            )
        )

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

            else:
                user_data = None
                with contextlib.suppress(KeyError):
                    user_data = await self.middleware.call('dscache.get_uncached_user', user)

                if not user_data:
                    verrors.add(
                        f'{schema}.user',
                        'Specified user does not exist'
                    )

        command = data.get('command')
        if not command:
            verrors.add(
                f'{schema}.command',
                'Please specify a command for cronjob task.'
            )

        return verrors, data

    @accepts(
        Dict(
            'cron_job_create',
            Bool('enabled'),
            Bool('stderr', default=False),
            Bool('stdout', default=True),
            Cron(
                'schedule',
                defaults={'minute': '00'}
            ),
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

        return await self._get_instance(data['id'])

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

        return await self._get_instance(id)

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

    @accepts(
        Int('id'),
        Bool('skip_disabled', default=False),
    )
    @returns()
    @job(lock=lambda args: f'cron_job_run_{args[0]}', logs=True, lock_queue_size=1)
    def run(self, job, id, skip_disabled):
        """
        Job to run cronjob task of `id`.
        """
        def __cron_log(line):
            job.logs_fd.write(line)
            syslog.syslog(syslog.LOG_INFO, line.decode())

        cron_task = self.middleware.call_sync('cronjob.get_instance', id)
        if skip_disabled and not cron_task['enabled']:
            raise CallError('Cron job is disabled', errno.EINVAL)

        cron_cmd = ' '.join(
            self.middleware.call_sync(
                'cronjob.construct_cron_command', cron_task['schedule'], cron_task['user'],
                cron_task['command'], cron_task['stdout'], cron_task['stderr']
            )[7:]
        )

        job.set_progress(
            10,
            'Executing Cron Task'
        )

        syslog.openlog('cron', facility=syslog.LOG_CRON)

        syslog.syslog(syslog.LOG_INFO, f'({cron_task["user"]}) CMD ({cron_cmd})')

        cp = run_command_with_user_context(
            cron_cmd, cron_task['user'], __cron_log
        )

        syslog.closelog()

        job.set_progress(
            85,
            'Executed Cron Task'
        )

        if cp.stdout:
            email = (
                self.middleware.call_sync('user.query', [['username', '=', cron_task['user']]], {'get': True})
            )['email']
            stdout = cp.stdout.decode()
            if email:
                mail_job = self.middleware.call_sync(
                    'mail.send', {
                        'subject': 'CronTask Run',
                        'text': stdout,
                        'to': [email]
                    }
                )

                job.set_progress(
                    95,
                    'Sending mail for Cron Task output'
                )

                mail_job.wait_sync()
                if mail_job.error:
                    job.logs_fd.write(f'Failed to send email for CronTask run: {mail_job.error}'.encode())
            else:
                job.set_progress(
                    95,
                    'Email for root user not configured. Skipping sending mail.'
                )

            job.logs_fd.write(f'Executed CronTask - {cron_cmd}: {stdout}'.encode())

        if cp.returncode:
            raise CallError(f'CronTask "{cron_cmd}" exited with {cp.returncode} (non-zero) exit status.')

        job.set_progress(
            100,
            'Execution of Cron Task complete.'
        )
