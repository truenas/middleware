import asyncio
import os
import stat
import subprocess
from typing import Literal

from middlewared.api import api_method
from middlewared.api.base import BaseModel
from middlewared.api.current import (
    InitShutdownScriptEntry, InitShutdownScriptCreateArgs, InitShutdownScriptCreateResult,
    InitShutdownScriptUpdateArgs, InitShutdownScriptUpdateResult, InitShutdownScriptDeleteArgs,
    InitShutdownScriptDeleteResult,
)
from middlewared.service import CRUDService, job, private
from middlewared.service_exception import CallError, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import run


class InitShutdownScriptModel(sa.Model):
    __tablename__ = 'tasks_initshutdown'

    id = sa.Column(sa.Integer(), primary_key=True)
    ini_type = sa.Column(sa.String(15), default='command')
    ini_command = sa.Column(sa.String(300))
    ini_script = sa.Column(sa.String(255), nullable=True)
    ini_when = sa.Column(sa.String(15))
    ini_enabled = sa.Column(sa.Boolean(), default=True)
    ini_timeout = sa.Column(sa.Integer(), default=10)
    ini_comment = sa.Column(sa.String(255))


class InitShutdownScriptExecuteInitTasksArgs(BaseModel):
    when: Literal["PREINIT", "POSTINIT", "SHUTDOWN"]


class InitShutdownScriptExecuteInitTasksResult(BaseModel):
    result: None


class InitShutdownScriptService(CRUDService):

    class Config:
        datastore = 'tasks.initshutdown'
        datastore_prefix = 'ini_'
        datastore_extend = 'initshutdownscript.init_shutdown_script_extend'
        cli_namespace = 'system.init_shutdown_script'
        entry = InitShutdownScriptEntry
        role_prefix = 'SYSTEM_CRON'

    @api_method(InitShutdownScriptCreateArgs, InitShutdownScriptCreateResult)
    async def do_create(self, data):
        """
        Create an initshutdown script task.

        `type` indicates if a command or script should be executed at `when`.

        There are three choices for `when`:

        1) PREINIT - This is early in the boot process before all the services have started
        2) POSTINIT - This is late in the boot process when most of the services have started
        3) SHUTDOWN - This is on shutdown

        `timeout` is an integer value which indicates time in seconds which the system should wait for the execution
        of script/command. It should be noted that a hard limit for a timeout is configured by the base OS, so when
        a script/command is set to execute on SHUTDOWN, the hard limit configured by the base OS is changed adding
        the timeout specified by script/command so it can be ensured that it executes as desired and is not interrupted
        by the base OS's limit.
        """
        await self.validate(data, 'init_shutdown_script_create')
        await self.init_shutdown_script_compress(data)
        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )
        return await self.get_instance(data['id'])

    @api_method(InitShutdownScriptUpdateArgs, InitShutdownScriptUpdateResult)
    async def do_update(self, id_, data):
        """
        Update initshutdown script task of `id`.
        """
        old = await self.get_instance(id_)
        new = old.copy()
        new.update(data)
        await self.validate(new, 'init_shutdown_script_update')
        await self.init_shutdown_script_compress(new)
        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id_,
            new,
            {'prefix': self._config.datastore_prefix}
        )
        return await self.get_instance(new['id'])

    @api_method(InitShutdownScriptDeleteArgs, InitShutdownScriptDeleteResult)
    async def do_delete(self, id_):
        """
        Delete init/shutdown task of `id`.
        """
        return await self.middleware.call('datastore.delete', self._config.datastore, id_)

    @private
    async def init_shutdown_script_extend(self, data):
        data['type'] = data['type'].upper()
        data['when'] = data['when'].upper()
        return data

    @private
    async def init_shutdown_script_compress(self, data):
        data['type'] = data['type'].lower()
        data['when'] = data['when'].lower()
        return data

    @private
    async def validate(self, data, schema_name):
        verrors = ValidationErrors()
        if data['type'] == 'COMMAND' and not data.get('command'):
            verrors.add(f'{schema_name}.command', 'This field is required')
        elif data['type'] == 'SCRIPT':
            if not data.get('script'):
                verrors.add(f'{schema_name}.script', 'This field is required')
            else:
                try:
                    obj = await self.middleware.call('filesystem.stat', data['script'])
                except CallError as e:
                    verrors.add(f'{schema_name}.script', e.errmsg, e.errno)
                except Exception as e:
                    verrors.add(f'{schema_name}.script', str(e))
                else:
                    if obj['type'] != 'FILE':
                        verrors.add(f'{schema_name}.script', 'Script must be a regular file not {obj["type"]!r}')
                    elif not bool(obj['mode'] & stat.S_IXUSR):
                        verrors.add(f'{schema_name}.script', 'Script must have execute bit set for the user')

        verrors.check()

    @private
    def get_cmd(self, task):
        if task['type'] == 'COMMAND':
            return task['command']
        elif task['type'] == 'SCRIPT' and os.path.exists(task['script']):
            return f'exec {task["script"]}'

    @private
    async def execute_task(self, task):
        cmd = await self.middleware.run_in_thread(self.get_cmd, task)
        if not cmd:
            return

        try:
            proc = await run(['sh', '-c', cmd], stderr=subprocess.STDOUT, check=False)
            if proc.returncode:
                self.logger.debug('Failed to execute %r with error %r', cmd, proc.stdout.decode())
        except Exception:
            self.logger.debug('Unexpected failure executing %r', cmd, exc_info=True)

    @api_method(InitShutdownScriptExecuteInitTasksArgs, InitShutdownScriptExecuteInitTasksResult, private=True)
    @job()
    async def execute_init_tasks(self, job, when):
        tasks = await self.middleware.call('initshutdownscript.query', [
                ['enabled', '=', True],
                ['when', '=', when]
        ])
        tasks_len = len(tasks)

        for idx, task in enumerate(tasks):
            cmd = task['command'] if task['type'] == 'COMMAND' else task['script']
            try:
                await asyncio.wait_for(self.middleware.create_task(self.execute_task(task)), timeout=task['timeout'])
            except asyncio.TimeoutError:
                self.logger.debug('Timed out running %s: %r', task['type'], cmd)
            finally:
                job.set_progress((100 / tasks_len) * (idx + 1))

        job.set_progress(100, f'Completed tasks for {when}')
