# Copyright 2017 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

import asyncio
import asyncssh
import glob
import os
import queue
import re
import shlex
import subprocess
import syslog

from multiprocessing import Process, Queue, Value

from middlewared.schema import accepts, Bool, Cron, Dict, Str, Int, List, Patch
from middlewared.validators import Range, Match
from middlewared.service import (
    CallError, CRUDService, SystemServiceService, ValidationErrors,
    job, item_method, private,
)
from middlewared.utils import setusercontext


class RsyncdService(SystemServiceService):

    class Config:
        service = "rsync"
        service_model = 'rsyncd'
        datastore_prefix = "rsyncd_"

    @accepts(Dict(
        'rsyncd_update',
        Int('port', validators=[Range(min=1, max=65535)]),
        Str('auxiliary'),
        update=True
    ))
    async def do_update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        await self._update_service(old, new)

        return new


class RsyncModService(CRUDService):

    class Config:
        datastore = 'services.rsyncmod'
        datastore_prefix = 'rsyncmod_'

    @accepts(Dict(
        'rsyncmod_create',
        Str('name', validators=[Match(r'[^/\]]')]),
        Str('comment'),
        Str('path'),
        Str('mode'),
        Int('maxconn'),
        Str('user'),
        Str('group'),
        List('hostsallow', items=[Str('hostsallow')], default=[]),
        List('hostsdeny', items=[Str('hostdeny')], default=[]),
        Str('auxiliary'),
        register=True,
    ))
    async def do_create(self, data):
        if data.get("hostsallow"):
            data["hostsallow"] = " ".join(data["hostsallow"])
        else:
            data["hostsallow"] = ""

        if data.get("hostsdeny"):
            data["hostsdeny"] = " ".join(data["hostsdeny"])
        else:
            data["hostsdeny"] = ""

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )
        await self._service_change('rsync', 'reload')
        return data

    @accepts(Int('id'), Patch('rsyncmod_create', 'rsyncmod_update', ('attr', {'update': True})))
    async def do_update(self, id, data):
        module = await self.middleware.call(
            'datastore.query',
            self._config.datastore,
            [('id', '=', id)],
            {'prefix': self._config.datastore_prefix, 'get': True}
        )
        module.update(data)

        module["hostsallow"] = " ".join(module["hostsallow"])
        module["hostsdeny"] = " ".join(module["hostsdeny"])

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            data,
            {'prefix': self._config.datastore_prefix}
        )
        await self._service_change('rsync', 'reload')

        return module

    @accepts(Int('id'))
    async def do_delete(self, id):
        return await self.middleware.call('datastore.delete', self._config.datastore, id)


def _run_command(user, commandline, q, rv):
    setusercontext(user)

    os.environ['PATH'] = (
        '/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:/root/bin'
    )
    proc = subprocess.Popen(
        commandline, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )

    # logger(1) does not honor original exit value so we use syslog module instead
    syslog.openlog(ident='rsync')
    while True:
        line = proc.stdout.readline()
        if line == b'':
            break
        try:
            q.put(line, False)
        except queue.Full:
            pass
        syslog.syslog(syslog.LOG_NOTICE, line.decode())
    syslog.closelog()
    proc.communicate()
    rv.value = proc.returncode
    q.put(None)


class RsyncTaskService(CRUDService):

    class Config:
        datastore = 'tasks.rsync'
        datastore_prefix = 'rsync_'
        datastore_extend = 'rsynctask.rsync_task_extend'

    @private
    async def rsync_task_extend(self, data):
        data['extra'] = list(filter(None, re.split(r"\s+", data["extra"])))
        Cron.convert_db_format_to_schedule(data)
        return data

    @private
    async def validate_rsync_task(self, data, schema):
        verrors = ValidationErrors()

        # Windows users can have spaces in their usernames
        # http://www.freebsd.org/cgi/query-pr.cgi?pr=164808

        username = data.get('user')
        if ' ' in username:
            verrors.add(f'{schema}.user', 'User names cannot have spaces')
            raise verrors

        user = await self.middleware.call(
            'notifier.get_user_object',
            username
        )
        if not user:
            verrors.add(f'{schema}.user', f'Provided user "{username}" does not exist')
            raise verrors

        remote_host = data.get('remotehost')
        if not remote_host:
            verrors.add(f'{schema}.remotehost', 'Please specify a remote host')

        if data.get('extra'):
            data['extra'] = ' '.join(data['extra'])
        else:
            data['extra'] = ''

        mode = data.get('mode')
        if not mode:
            verrors.add(f'{schema}.mode', 'This field is required')

        remote_module = data.get('remotemodule')
        if mode == 'module' and not remote_module:
            verrors.add(f'{schema}.remotemodule', 'This field is required')

        if mode == 'ssh':
            remote_port = data.get('remoteport')
            if not remote_port:
                verrors.add(f'{schema}.remoteport', 'This field is required')

            remote_path = data.get('remotepath')
            if not remote_path:
                verrors.add(f'{schema}.remotepath', 'This field is required')

            search = os.path.join(user.pw_dir, '.ssh', 'id_[edr]*')
            exclude_from_search = os.path.join(user.pw_dir, '.ssh', 'id_[edr]*pub')
            key_files = set(glob.glob(search)) - set(glob.glob(exclude_from_search))
            if not key_files:
                verrors.add(
                    f'{schema}.user',
                    'In order to use rsync over SSH you need a user'
                    ' with a private key (DSA/ECDSA/RSA) set up in home dir.'
                )
            else:
                for file in glob.glob(search):
                    if '.pub' not in file:
                        # file holds a private key and it's permissions should be 600
                        if os.stat(file).st_mode & 0o077 != 0:
                            verrors.add(
                                f'{schema}.user',
                                f'Permissions {oct(os.stat(file).st_mode & 0o777)} for {file} are too open. Please '
                                f'correct them by running chmod 600 {file}'
                            )

            if(
                data.get('validate_rpath') and
                remote_path and
                remote_host and
                remote_port
            ):
                if '@' in remote_host:
                    remote_username, remote_host = remote_host.rsplit('@', 1)
                else:
                    remote_username = username

                try:
                    with (await asyncio.wait_for(asyncssh.connect(
                            remote_host,
                            port=remote_port,
                            username=remote_username,
                            client_keys=key_files,
                            known_hosts=None
                    ), timeout=5)) as conn:

                        await conn.run(f'test -d {remote_path}', check=True)

                except asyncio.TimeoutError:

                    verrors.add(
                        f'{schema}.remotehost',
                        'SSH timeout occurred. Remote path cannot be validated.'
                    )

                except OSError as e:

                    if e.errno == 113:
                        verrors.add(
                            f'{schema}.remotehost',
                            f'Connection to the remote host {remote_host} on port {remote_port} failed.'
                        )
                    else:
                        verrors.add(
                            f'{schema}.remotehost',
                            e.__str__()
                        )

                except asyncssh.DisconnectError as e:

                    verrors.add(
                        f'{schema}.remotehost',
                        f'Disconnect Error[ error code {e.code} ] was generated when trying to '
                        f'communicate with remote host {remote_host} and remote user {remote_username}.'
                    )

                except asyncssh.ProcessError as e:

                    if e.code == '1':
                        verrors.add(
                            f'{schema}.remotepath',
                            'The Remote Path you specified does not exist or is not a directory.'
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
            elif data.get('validate_rpath'):
                verrors.add(
                    f'{schema}.remotepath',
                    'Remote path could not be validated because of missing fields'
                )

        data.pop('validate_rpath', None)

        return verrors, data

    @accepts(Dict(
        'rsync_task_create',
        Str('path'),
        Str('user', required=True),
        Str('remotehost'),
        Int('remoteport'),
        Str('mode'),
        Str('remotemodule'),
        Str('remotepath'),
        Bool('validate_rpath'),
        Str('direction'),
        Str('desc'),
        Cron('schedule'),
        Bool('recursive'),
        Bool('times'),
        Bool('compress'),
        Bool('archive'),
        Bool('delete'),
        Bool('quiet'),
        Bool('preserveperm'),
        Bool('preserveattr'),
        Bool('delayupdates'),
        List('extra', items=[Str('extra')]),
        Bool('enabled'),
        register=True,
    ))
    async def do_create(self, data):
        verrors, data = await self.validate_rsync_task(data, 'rsync_task_create')
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
        Patch('rsync_task_create', 'rsync_task_update', ('attr', {'update': True}))
    )
    async def do_update(self, id, data):
        old = await self.query(filters=[('id', '=', id)], options={'get': True})

        new = old.copy()
        new.update(data)

        verrors, data = await self.validate_rsync_task(new, 'rsync_task_update')
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
        await self.middleware.call('service.restart', 'cron')

        return await self.query(filters=[('id', '=', id)], options={'get': True})

    @accepts(Int('id'))
    async def do_delete(self, id):
        res = await self.middleware.call('datastore.delete', self._config.datastore, id)
        await self.middleware.call('service.restart', 'cron')
        return res

    @private
    async def commandline(self, id):
        """
        Helper method to generate the rsync command avoiding code duplication.
        """
        rsync = await self._get_instance(id)
        line = [
            '/usr/bin/lockf', '-s', '-t', '0', '-k', rsync["path"], '/usr/local/bin/rsync'
        ]
        for name, flag in (
            ('archive', '-a'),
            ('compress', '-z'),
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

        # Do not use username if one is specified in host field
        # See #5096 for more details
        if '@' in rsync['remotehost']:
            remote = rsync['remotehost']
        else:
            remote = f'"{rsync["user"]}"@{rsync["remotehost"]}'

        if rsync['mode'] == 'module':
            module_args = [rsync["path"], f'{remote}::"{rsync["remotemodule"]}"']
            if rsync['direction'] != 'push':
                module_args.reverse()
            line += module_args
        else:
            line += [
                '-e',
                f'ssh -p {rsync["remoteport"]} -o BatchMode=yes -o StrictHostKeyChecking=yes'
            ]
            path_args = [rsync["path"], f'{remote}:{rsync["remotepath"]}']
            if rsync['direction'] != 'push':
                path_args.reverse()
            line += path_args

        if rsync['quiet']:
            line += ['>', '/dev/null', '2>&1']
        return ' '.join([shlex.quote(arg) for arg in line])

    @item_method
    @accepts(Int('id'))
    @job(lock=lambda args: args[-1], logs=True)
    def run(self, job, id):
        """
        Job to run rsync task of `id`.

        Output is saved to job log excerpt as well as syslog.
        """
        rsync = self.middleware.call_sync('rsynctask._get_instance', id)
        commandline = self.middleware.call_sync('rsynctask.commandline', id)
        q = Queue()
        rv = Value('i')
        p = Process(target=_run_command, args=(rsync['user'], commandline, q, rv), daemon=True)
        p.start()
        while p.is_alive() or not q.empty():
            try:
                get = q.get(True, 2)
                if get is None:
                    break
                job.logs_fd.write(get)
            except queue.Empty:
                pass
        p.join()
        if rv.value != 0:
            raise CallError(
                f'rsync command returned {rv.value}. Check logs for further information.'
            )
