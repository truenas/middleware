import contextlib
import errno

from middlewared.api import api_method
from middlewared.api.current import (
    CronJobEntry, CronJobCreateArgs, CronJobCreateResult, CronJobUpdateArgs, CronJobUpdateResult, CronJobDeleteArgs,
    CronJobDeleteResult, CronJobRunArgs, CronJobRunResult
)
from middlewared.schema import Cron
from middlewared.service import CallError, CRUDService, job, private, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.user_context import run_command_with_user_context


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
        entry = CronJobEntry
        role_prefix = 'SYSTEM_CRON'

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
                    user_data = await self.middleware.call('user.get_user_obj', {'username': user})

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

    @api_method(CronJobCreateArgs, CronJobCreateResult)
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
        verrors.check()

        Cron.convert_schedule_to_db_format(data)

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)

        return await self.get_instance(data['id'])

    @api_method(CronJobUpdateArgs, CronJobUpdateResult)
    async def do_update(self, id_, data):
        """
        Update cronjob of `id`.
        """
        # FIXME: Use `await self.query` once query endpoints are fully converted.
        task_data = await self.middleware.call('cronjob.query', [('id', '=', id_)], {'get': True})
        original_data = task_data.copy()
        task_data.update(data)
        verrors, task_data = await self.validate_data(task_data, 'cron_job_update')

        verrors.check()

        Cron.convert_schedule_to_db_format(task_data)
        Cron.convert_schedule_to_db_format(original_data)

        if len(set(task_data.items()) ^ set(original_data.items())) > 0:

            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                id_,
                task_data,
                {'prefix': self._config.datastore_prefix}
            )

            await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)

        return await self.get_instance(id_)

    @api_method(CronJobDeleteArgs, CronJobDeleteResult)
    async def do_delete(self, id_):
        """
        Delete cronjob of `id`.
        """
        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id_
        )

        await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)

        return response

    @api_method(CronJobRunArgs, CronJobRunResult, roles=['SYSTEM_CRON_WRITE'])
    @job(lock=lambda args: f'cron_job_run_{args[0]}', logs=True, lock_queue_size=1)
    def run(self, job, id_, skip_disabled):
        """
        Job to run cronjob task of `id`.
        """
        cron_task = self.middleware.call_sync('cronjob.get_instance', id_)
        if skip_disabled and not cron_task['enabled']:
            raise CallError('Cron job is disabled', errno.EINVAL)

        cron_cmd = ' '.join(
            self.middleware.call_sync(
                'cronjob.construct_cron_command', cron_task['schedule'], cron_task['user'],
                cron_task['command'], cron_task['stdout'], cron_task['stderr']
            )[7:]
        )

        job.set_progress(10, 'Executing Cron Task')

        cp = run_command_with_user_context(cron_cmd, cron_task['user'], callback=job.logs_fd.write)

        job.set_progress(85, 'Executed Cron Task')
        if cp.stdout:
            email = (
                self.middleware.call_sync('user.query', [['username', '=', cron_task['user']]], {'get': True})
            )['email']
            stdout = cp.stdout.decode()
            if email:
                text = (
                    'The command:\n\n' +
                    cron_task['command'] + '\n\n' +
                    'Produced the following output:\n\n' +
                    stdout.rstrip() + '\n\n' +
                    "If you don't wish to receive these e-mails, please go to your Cron Job options and check " +
                    '"Hide Standard Output" and "Hide Standard Error" checkboxes.'
                )

                mail_job = self.middleware.call_sync(
                    'mail.send', {
                        'subject': 'Cron Job Run',
                        'text': text,
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
