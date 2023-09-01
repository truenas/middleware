import asyncio
import os
import stat
import subprocess
import tempfile

from middlewared.schema import Bool, Dict, File, Int, Patch, Str, ValidationErrors, accepts
from middlewared.service import CRUDService, job, private
import middlewared.sqlalchemy as sa
from middlewared.utils import Popen
from middlewared.validators import Range


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
    ini_script_text = sa.Column(sa.Text())


class InitShutdownScriptService(CRUDService):

    class Config:
        datastore = 'tasks.initshutdown'
        datastore_prefix = 'ini_'
        datastore_extend = 'initshutdownscript.init_shutdown_script_extend'
        cli_namespace = 'system.init_shutdown_script'

    ENTRY = Patch(
        'init_shutdown_script_create', 'init_shutdown_script_entry',
        ('add', Int('id', required=True)),
    )

    @accepts(Dict(
        'init_shutdown_script_create',
        Str('type', enum=['COMMAND', 'SCRIPT'], required=True),
        Str('command', null=True),
        Str('script_text', null=True),
        File('script', null=True),
        Str('when', enum=['PREINIT', 'POSTINIT', 'SHUTDOWN'], required=True),
        Bool('enabled', default=True),
        Int('timeout', default=10),
        Str('comment', default='', validators=[Range(max_=255)]),
        register=True,
    ))
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

        if data['type'] == 'COMMAND':
            if not data.get('command'):
                verrors.add(f'{schema_name}.command', 'This field is required')
            else:
                data['script_text'] = ''
                data['script'] = ''

        if data['type'] == 'SCRIPT':
            if data.get('script') and data.get('script_text'):
                verrors.add(f'{schema_name}.script', 'Only one of two fields should be provided')
            elif not data.get('script') and not data.get('script_text'):
                # IDEA may be it's worth putting both fields validations errors to verrors
                # e.g.
                # verrors.add(f'{schema_name}.script', 'This field is required')
                # verrors.add(f'{schema_name}.script_text', 'This field is required')
                verrors.add(f'{schema_name}.script', "Either 'script' or 'script_text' field is required")
            elif data.get('script') and not data.get('script_text'):
                data['command'] = ''
                data['script_text'] = ''
            else:
                data['command'] = ''
                data['script'] = ''

        verrors.check()

    @private
    def write_script_text(self, script_text):
        with tempfile.NamedTemporaryFile(delete=False, mode='w') as f:
            f.write(script_text)
            os.fchmod(f.fileno(), stat.S_IRWXU)
            return f.name

    @private
    def script_already_exists(self, script):
        return os.path.exists(script) and os.access(script, os.X_OK)

    @private
    def rem_tmp_script(self, script):
        try:
            os.unlink(script)
        except FileNotFoundError:
            pass
        except Exception:
            self.logger.debug('Unexpected failure removing %r', script, exc_info=True)

    @private
    async def execute_task(self, task):
        task_type = task['type']
        cmd = tmp_script = None

        if task_type == 'COMMAND':
            cmd = task['command']
        elif task_type == 'SCRIPT' and task['script_text']:
            tmp_script = await self.middleware.run_in_thread(self.write_script_text, task['script_text'])
            cmd = f'exec {tmp_script}'
        elif await self.middleware.run_in_thread(self.script_already_exists, task['script']):
            cmd = f'exec {task["script"]}'
        else:
            return

        try:
            proc = await Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                close_fds=True
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode:
                self.logger.debug('Failed to execute %r with error %r', cmd, stdout.decode())
        except Exception:
            self.logger.debug('Unexpected failure executing %r', cmd, exc_info=True)
        finally:
            if tmp_script is not None:
                await self.middleware.run_in_thread(self.rem_tmp_script, tmp_script)

    @private
    @accepts(
        Str('when')
    )
    @job()
    async def execute_init_tasks(self, job, when):
        tasks = await self.middleware.call('initshutdownscript.query', [
                ['enabled', '=', True],
                ['when', '=', when]
        ])
        tasks_len = len(tasks)

        for idx, task in enumerate(tasks):
            try:
                await asyncio.wait_for(self.middleware.create_task(self.execute_task(task)), timeout=task['timeout'])
            except asyncio.TimeoutError:
                if task['type'] == 'COMMAND':
                    cmd = task['command']
                elif task['type'] == 'SCRIPT' and task['script_text']:
                    cmd = task['comment']
                elif task['type'] == 'SCRIPT' and task['script']:
                    cmd = task['script']
                else:
                    cmd = ''
                self.logger.debug('Timed out running %s: %r', task['type'], cmd)
            finally:
                job.set_progress((100 / tasks_len) * (idx + 1))

        job.set_progress(100, f'Completed tasks for {when}')
