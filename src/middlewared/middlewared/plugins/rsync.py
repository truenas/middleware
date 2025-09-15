import asyncio
import asyncssh
import contextlib
import enum
import glob
import os
import pathlib
import shlex
import tempfile

from middlewared.api import api_method
from middlewared.api.current import (
    RsyncTaskEntry,
    RsyncTaskCreateArgs, RsyncTaskCreateResult,
    RsyncTaskUpdateArgs, RsyncTaskUpdateResult,
    RsyncTaskDeleteArgs, RsyncTaskDeleteResult,
    RsyncTaskRunArgs, RsyncTaskRunResult,
)
from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.plugins.rsync_.utils import get_host_key_file_contents_from_ssh_credentials
from middlewared.service import (
    CallError, ValidationErrors, job, item_method, private, TaskPathService,
)
import middlewared.sqlalchemy as sa
from middlewared.utils import run
from middlewared.utils.cron import convert_db_format_to_schedule, convert_schedule_to_db_format
from middlewared.utils.user_context import run_command_with_user_context
from middlewared.utils.service.task_state import TaskStateMixin


RSYNC_PATH_LIMIT = 1023


class RsyncReturnCode(enum.Enum):
    # from rsync's "errcode.h"
    OK = 0
    SYNTAX = 1         # syntax or usage error
    PROTOCOL = 2       # protocol incompatibility
    FILESELECT = 3     # errors selecting input/output files, dirs
    UNSUPPORTED = 4    # requested action not supported
    STARTCLIENT = 5    # error starting client-server protocol
    SOCKETIO = 10      # error in socket IO
    FILEIO = 11        # error in file IO
    STREAMIO = 12      # error in rsync protocol data stream
    MESSAGEIO = 13     # errors with program diagnostics
    IPC = 14           # error in IPC code
    CRASHED = 15       # sibling crashed
    TERMINATED = 16    # sibling terminated abnormally
    SIGNAL1 = 19       # status returned when sent SIGUSR1
    SIGNAL = 20        # status returned when sent SIGINT, SIGTERM, SIGHUP
    WAITCHILD = 21     # some error returned by waitpid()
    MALLOC = 22        # error allocating core memory buffers
    PARTIAL = 23       # partial transfer
    VANISHED = 24      # file(s) vanished on sender side
    DEL_LIMIT = 25     # skipped some deletes due to --max-delete
    TIMEOUT = 30       # timeout in data send/receive
    CONTIMEOUT = 35    # timeout waiting for daemon connection

    @classmethod
    def nonfatals(cls):
        return tuple([rc.value for rc in [
            cls.OK,
            cls.VANISHED,
            cls.DEL_LIMIT
        ]])


class RsyncTaskModel(sa.Model):
    __tablename__ = 'tasks_rsync'

    id = sa.Column(sa.Integer(), primary_key=True)
    rsync_path = sa.Column(sa.String(255))
    rsync_remotehost = sa.Column(sa.String(120), nullable=True)
    rsync_remoteport = sa.Column(sa.SmallInteger(), nullable=True)
    rsync_remotemodule = sa.Column(sa.String(120), nullable=True)
    rsync_ssh_credentials_id = sa.Column(sa.ForeignKey('system_keychaincredential.id'), index=True, nullable=True)
    rsync_desc = sa.Column(sa.String(120))
    rsync_minute = sa.Column(sa.String(100))
    rsync_hour = sa.Column(sa.String(100))
    rsync_daymonth = sa.Column(sa.String(100))
    rsync_month = sa.Column(sa.String(100))
    rsync_dayweek = sa.Column(sa.String(100))
    rsync_user = sa.Column(sa.String(60))
    rsync_recursive = sa.Column(sa.Boolean())
    rsync_times = sa.Column(sa.Boolean())
    rsync_compress = sa.Column(sa.Boolean())
    rsync_archive = sa.Column(sa.Boolean())
    rsync_delete = sa.Column(sa.Boolean())
    rsync_quiet = sa.Column(sa.Boolean())
    rsync_preserveperm = sa.Column(sa.Boolean())
    rsync_preserveattr = sa.Column(sa.Boolean())
    rsync_extra = sa.Column(sa.Text())
    rsync_enabled = sa.Column(sa.Boolean())
    rsync_mode = sa.Column(sa.String(20))
    rsync_remotepath = sa.Column(sa.String(255))
    rsync_direction = sa.Column(sa.String(10))
    rsync_delayupdates = sa.Column(sa.Boolean())
    rsync_job = sa.Column(sa.JSON(None))


class RsyncTaskService(TaskPathService, TaskStateMixin):

    share_task_type = 'Rsync'
    task_state_methods = ['rsynctask.run']

    class Config:
        datastore = 'tasks.rsync'
        datastore_prefix = 'rsync_'
        datastore_extend = 'rsynctask.rsync_task_extend'
        datastore_extend_context = 'rsynctask.rsync_task_extend_context'
        cli_namespace = 'task.rsync'
        entry = RsyncTaskEntry
        role_prefix = 'SNAPSHOT_TASK'

    @private
    async def rsync_task_extend(self, data, context):
        try:
            data['extra'] = shlex.split(data['extra'].replace('"', r'"\"').replace("'", r'"\"'))
        except ValueError:
            # This is to handle the case where the extra value is misconfigured for old cases
            # Moving on, we are going to verify that it can be split successfully using shlex
            data['extra'] = data['extra'].split()

        convert_db_format_to_schedule(data)
        if job := await self.get_task_state_job(context['task_state'], data['id']):
            data['job'] = job
        return data

    @private
    async def rsync_task_extend_context(self, rows, extra):
        return {
            'task_state': await self.get_task_state_context(),
        }

    @private
    async def validate_rsync_task(self, data, schema):
        verrors = ValidationErrors()

        # Windows users can have spaces in their usernames
        # http://www.freebsd.org/cgi/query-pr.cgi?pr=164808

        username = data.get('user')
        if ' ' in username:
            verrors.add(f'{schema}.user', 'User names cannot have spaces')
            raise verrors

        user = None
        with contextlib.suppress(KeyError):
            user = await self.middleware.call('user.get_user_obj', {'username': username})

        if not user:
            verrors.add(f'{schema}.user', f'Provided user "{username}" does not exist')
            raise verrors

        await self.validate_path_field(data, schema, verrors)

        data['extra'] = ' '.join(data['extra'])
        try:
            shlex.split(data['extra'].replace('"', r'"\"').replace("'", r'"\"'))
        except ValueError as e:
            verrors.add(f'{schema}.extra', f'Please specify valid value: {e}')

        if data['mode'] == 'MODULE':
            if not data['remotehost']:
                verrors.add(f'{schema}.remotehost', 'This field is required')

            if not data['remotemodule']:
                verrors.add(f'{schema}.remotemodule', 'This field is required')

            if data['ssh_credentials']:
                verrors.add(f'{schema}.ssh_credentials', "SSH credentials can't be used when mode is MODULE")

        if data['mode'] == 'SSH':
            connect_kwargs = None
            if data['ssh_credentials']:
                try:
                    ssh_credentials = await self.middleware.call(
                        'keychaincredential.get_of_type',
                        data['ssh_credentials'],
                        'SSH_CREDENTIALS',
                    )
                except CallError as e:
                    verrors.add(f'{schema}.ssh_credentials', e.errmsg)
                else:
                    ssh_keypair = await self.middleware.call(
                        'keychaincredential.get_of_type',
                        ssh_credentials['attributes']['private_key'],
                        'SSH_KEY_PAIR',
                    )
                    connect_kwargs = {
                        "host": ssh_credentials['attributes']['host'],
                        "port": ssh_credentials['attributes']['port'],
                        'username': ssh_credentials['attributes']['username'],
                        'client_keys': [asyncssh.import_private_key(ssh_keypair['attributes']['private_key'])],
                        'known_hosts': asyncssh.SSHKnownHosts(get_host_key_file_contents_from_ssh_credentials(
                            ssh_credentials['attributes'],
                        ))
                    }
            else:
                if not data['remotehost']:
                    verrors.add(f'{schema}.remotehost', 'This field is required')

                if not data['remoteport']:
                    verrors.add(f'{schema}.remoteport', 'This field is required')

                search = os.path.join(user['pw_dir'], '.ssh', 'id_[edr]*')
                exclude_from_search = os.path.join(user['pw_dir'], '.ssh', 'id_[edr]*pub')
                key_files = set(glob.glob(search)) - set(glob.glob(exclude_from_search))
                if not key_files:
                    verrors.add(
                        f'{schema}.user',
                        'In order to use rsync over SSH you need a user'
                        ' with a private key (DSA/ECDSA/RSA) set up in home dir.'
                    )
                else:
                    for file in set(key_files):
                        # file holds a private key and it's permissions should be 600
                        if os.stat(file).st_mode & 0o077 != 0:
                            verrors.add(
                                f'{schema}.user',
                                f'Permissions {str(oct(os.stat(file).st_mode & 0o777))[2:]} for {file} are too open. '
                                f'Please correct them by running chmod 600 {file}'
                            )
                            key_files.discard(file)

                    if key_files:
                        if '@' in data['remotehost']:
                            remote_username, remote_host = data['remotehost'].rsplit('@', 1)
                        else:
                            remote_username = username
                            remote_host = data['remotehost']

                        connect_kwargs = {
                            'host': remote_host,
                            'port': data['remoteport'],
                            'username': remote_username,
                            'client_keys': key_files,
                        }

            remote_path = data.get('remotepath')
            if not remote_path:
                verrors.add(f'{schema}.remotepath', 'This field is required')

            if data['enabled'] and connect_kwargs:
                ssh_dir_path = pathlib.Path(os.path.join(user['pw_dir'], '.ssh'))
                known_hosts_path = pathlib.Path(os.path.join(ssh_dir_path, 'known_hosts'))

                if 'known_hosts' not in connect_kwargs:
                    try:
                        try:
                            known_hosts_text = await self.middleware.run_in_thread(known_hosts_path.read_text)
                        except FileNotFoundError:
                            known_hosts_text = ''

                        known_hosts = asyncssh.SSHKnownHosts(known_hosts_text)
                    except Exception as e:
                        verrors.add(
                            f'{schema}.remotehost',
                            f'Failed to load {known_hosts_path}: {e}',
                        )
                    else:
                        if data['ssh_keyscan']:
                            if not known_hosts.match(connect_kwargs['host'], '', None)[0]:
                                if known_hosts_text and not known_hosts_text.endswith("\n"):
                                    known_hosts_text += '\n'

                                known_hosts_text += (await run(
                                    ['ssh-keyscan', '-p', str(connect_kwargs['port']), connect_kwargs['host']],
                                    encoding='utf-8',
                                    errors='ignore',
                                )).stdout

                                # If for whatever reason the dir does not exist, let's create it
                                # An example of this is when we run rsync tests we nuke the directory
                                def handle_ssh_dir():
                                    with contextlib.suppress(FileExistsError):
                                        ssh_dir_path.mkdir(0o700)

                                    os.chown(ssh_dir_path.absolute(), user['pw_uid'], user['pw_gid'])
                                    known_hosts_path.write_text(known_hosts_text)
                                    os.chown(known_hosts_path.absolute(), user['pw_uid'], user['pw_gid'])

                                await self.middleware.run_in_thread(handle_ssh_dir)

                                known_hosts = asyncssh.SSHKnownHosts(known_hosts_text)

                    if not verrors:
                        connect_kwargs['known_hosts'] = known_hosts

                verrors.check()

                if data['validate_rpath']:
                    try:
                        async with await asyncssh.connect(
                            **connect_kwargs,
                            options=asyncssh.SSHClientConnectionOptions(connect_timeout=5),
                        ) as conn:
                            print(await conn.run(f'test -d {shlex.quote(remote_path)}', check=True))
                    except asyncio.TimeoutError:
                        verrors.add(
                            f'{schema}.remotehost',
                            'SSH timeout occurred. Remote path cannot be validated.'
                        )
                    except OSError as e:
                        if e.errno == 113:
                            verrors.add(
                                f'{schema}.remotehost',
                                f'Connection to the remote host {connect_kwargs["host"]} on port '
                                f'{connect_kwargs["port"]} failed.'
                            )
                        else:
                            verrors.add(
                                f'{schema}.remotehost',
                                e.__str__()
                            )
                    except asyncssh.HostKeyNotVerifiable as e:
                        verrors.add(
                            f'{schema}.remotehost',
                            f'Failed to verify remote host key: {e.reason}',
                            CallError.ESSLCERTVERIFICATIONERROR,
                        )
                    except asyncssh.DisconnectError as e:
                        verrors.add(
                            f'{schema}.remotehost',
                            f'Disconnect Error [error code {e.code}: {e.reason}] was generated when trying to '
                            f'communicate with remote host {connect_kwargs["host"]} and remote user '
                            f'{connect_kwargs["username"]}.'
                        )
                    except asyncssh.ProcessError as e:
                        if e.code == 1:
                            verrors.add(
                                f'{schema}.remotepath',
                                'The Remote Path you specified does not exist or is not a directory. '
                                'Either create one yourself on the remote machine or uncheck the '
                                'validate_rpath field'
                            )
                        else:
                            verrors.add(
                                f'{schema}.remotepath',
                                f'Connection to Remote Host was successful but failed to verify '
                                f'Remote Path. {e.__str__()}'
                            )
                    except asyncssh.Error as e:
                        if e.__class__.__name__ in e.__str__():
                            exception_reason = e.__str__()
                        else:
                            exception_reason = e.__class__.__name__ + ' ' + e.__str__()
                        verrors.add(
                            f'{schema}.remotepath',
                            f'Remote Path could not be validated. An exception was raised. {exception_reason}'
                        )
                else:
                    if not known_hosts.match(connect_kwargs['host'], '', None)[0]:
                        verrors.add(
                            f'{schema}.remotehost',
                            f'Host key not found in {known_hosts_path}',
                            CallError.ESSLCERTVERIFICATIONERROR,
                        )

        data.pop('validate_rpath', None)
        data.pop('ssh_keyscan', None)

        return verrors, data

    @api_method(RsyncTaskCreateArgs, RsyncTaskCreateResult)
    async def do_create(self, data):
        """
        Create a Rsync Task.
        """
        verrors, data = await self.validate_rsync_task(data, 'rsync_task_create')
        verrors.check()

        convert_schedule_to_db_format(data)

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )
        await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)

        return await self.get_instance(data['id'])

    @api_method(RsyncTaskUpdateArgs, RsyncTaskUpdateResult)
    async def do_update(self, id_, data):
        """
        Update Rsync Task of `id`.
        """
        data.setdefault('validate_rpath', True)
        data.setdefault('ssh_keyscan', False)

        old = await self.get_instance(id_)
        old.pop(self.locked_field)
        old.pop('job')

        new = old.copy()
        if new['ssh_credentials']:
            new['ssh_credentials'] = new['ssh_credentials']['id']
        new.update(data)

        verrors, new = await self.validate_rsync_task(new, 'rsync_task_update')
        verrors.check()

        convert_schedule_to_db_format(new)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id_,
            new,
            {'prefix': self._config.datastore_prefix}
        )
        await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)

        return await self.get_instance(id_)

    @api_method(RsyncTaskDeleteArgs, RsyncTaskDeleteResult)
    async def do_delete(self, id_):
        """
        Delete Rsync Task of `id`.
        """
        res = await self.middleware.call('datastore.delete', self._config.datastore, id_)
        await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)
        return res

    @private
    @contextlib.contextmanager
    def commandline(self, id_):
        """
        Helper method to generate the rsync command avoiding code duplication.
        """
        rsync = self.middleware.call_sync('rsynctask.get_instance', id_)
        path = shlex.quote(rsync['path'])

        with contextlib.ExitStack() as exit_stack:
            line = ['rsync']
            for name, flag in (
                ('archive', '-a'),
                ('compress', '-zz'),
                ('delayupdates', '--delay-updates'),
                ('delete', '--delete-delay'),
                ('preserveattr', '-X'),
                ('preserveperm', '-p'),
                ('recursive', '-r'),
                ('times', '-t'),
            ):
                if rsync[name]:
                    line.append(flag)
            if rsync['extra']:
                line.append(' '.join(rsync['extra']))

            if not rsync['ssh_credentials']:
                # Do not use username if one is specified in host field
                # See #5096 for more details
                if '@' in rsync['remotehost']:
                    remote = rsync['remotehost']
                else:
                    remote = f'"{rsync["user"]}"@{rsync["remotehost"]}'

            if rsync['mode'] == 'MODULE':
                module_args = [path, f'rsync://{remote}/"{rsync["remotemodule"]}"']
                if rsync['direction'] != 'PUSH':
                    module_args.reverse()
                line += module_args
            else:
                if rsync['ssh_credentials']:
                    credentials = rsync['ssh_credentials']['attributes']
                    key_pair = self.middleware.call_sync(
                        'keychaincredential.get_of_type',
                        credentials['private_key'],
                        'SSH_KEY_PAIR',
                    )

                    remote = f'"{credentials["username"]}"@{credentials["host"]}'
                    port = credentials['port']

                    user = self.middleware.call_sync('user.get_user_obj', {'username': rsync['user']})

                    private_key_file = exit_stack.enter_context(tempfile.NamedTemporaryFile('w'))
                    os.fchmod(private_key_file.fileno(), 0o600)
                    os.fchown(private_key_file.fileno(), user['pw_uid'], user['pw_gid'])
                    private_key_file.write(key_pair['attributes']['private_key'])
                    private_key_file.flush()

                    host_key_file = exit_stack.enter_context(tempfile.NamedTemporaryFile('w'))
                    os.fchmod(host_key_file.fileno(), 0o600)
                    os.fchown(host_key_file.fileno(), user['pw_uid'], user['pw_gid'])
                    host_key_file.write(get_host_key_file_contents_from_ssh_credentials(credentials))
                    host_key_file.flush()

                    extra_args = f'-i {private_key_file.name} -o UserKnownHostsFile={host_key_file.name}'
                else:
                    port = rsync['remoteport']
                    extra_args = ''

                remote_username, remote_host = remote.rsplit('@', 1)
                if ':' in remote_host:
                    remote_host = f'[{remote_host}]'
                remote = f'{remote_username}@{remote_host}'

                line += [
                    '-e',
                    f'"ssh -p {port} -o BatchMode=yes -o StrictHostKeyChecking=yes {extra_args}"'
                ]
                path_args = [path, f'{remote}:{shlex.quote(rsync["remotepath"])}']
                if rsync['direction'] != 'PUSH':
                    path_args.reverse()
                line += path_args

            if rsync['quiet']:
                line += ['>', '/dev/null', '2>&1']

            yield ' '.join(line)

    @item_method
    @api_method(RsyncTaskRunArgs, RsyncTaskRunResult, roles=['SNAPSHOT_TASK_WRITE'])
    @job(lock=lambda args: args[-1], lock_queue_size=1, logs=True)
    def run(self, job, id_):
        """
        Job to run rsync task of `id`.

        Output is saved to job log excerpt (not syslog).
        """
        self.middleware.call_sync('network.general.will_perform_activity', 'rsync')

        rsync = self.middleware.call_sync('rsynctask.get_instance', id_)
        if rsync['locked']:
            self.middleware.call_sync('rsynctask.generate_locked_alert', id_)
            return

        with self.commandline(id_) as commandline:
            cp = run_command_with_user_context(
                commandline, rsync['user'], output=False, callback=lambda v: job.logs_fd.write(v),
            )

        for klass in ('RsyncSuccess', 'RsyncFailed') if not rsync['quiet'] else ():
            self.middleware.call_sync('alert.oneshot_delete', klass, rsync['id'])

        if cp.returncode not in RsyncReturnCode.nonfatals():
            err = None
            if cp.returncode == RsyncReturnCode.STREAMIO and rsync['compress']:
                err = (
                    "rsync command with compression enabled failed with STREAMIO error. "
                    "This may indicate that remote server lacks support for the new-style "
                    "compression used by TrueNAS."
                )

            if not rsync['quiet']:
                self.middleware.call_sync('alert.oneshot_create', 'RsyncFailed', {
                    'id': rsync['id'],
                    'direction': rsync['direction'],
                    'path': rsync['path'],
                })

            if err:
                msg = f'{err} Check logs for further information'
            else:
                try:
                    rc_name = RsyncReturnCode(cp.returncode).name
                except ValueError:
                    rc_name = 'UNKNOWN'

                msg = (
                    f'rsync command returned {cp.returncode} - {rc_name}. '
                    'Check logs for further information.'
                )
            raise CallError(msg)

        elif not rsync['quiet']:
            self.middleware.call_sync('alert.oneshot_create', 'RsyncSuccess', {
                'id': rsync['id'],
                'direction': rsync['direction'],
                'path': rsync['path'],
            })


class RsyncFSAttachmentDelegate(LockableFSAttachmentDelegate):
    name = 'rsync'
    title = 'Rsync Task'
    service_class = RsyncTaskService
    resource_name = 'path'

    async def restart_reload_services(self, attachments):
        await (await self.middleware.call('service.control', 'RESTART', 'cron')).wait(raise_error=True)


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', RsyncFSAttachmentDelegate(middleware))
    await middleware.call('network.general.register_activity', 'rsync', 'Rsync')
    await middleware.call('rsynctask.persist_task_state_on_job_complete')
