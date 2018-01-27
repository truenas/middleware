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

import os
import errno
import pwd
import re
import tempfile
import subprocess
import threading
import shutil
from collections import defaultdict
from middlewared.schema import accepts, Bool, Dict, Str, Int, Ref, List
from middlewared.validators import Range
from middlewared.service import (
    Service, job, CallError, CRUDService, SystemServiceService, ValidationError
)
from middlewared.logger import Logger


logger = Logger('rsync').getLogger()
RSYNC_PATH = '/usr/local/bin/rsync'


def demote(user):
    """
    Helper function to call the subprocess as the specific user.
    Taken from: https://gist.github.com/sweenzor/1685717
    Pass the function 'set_ids' to preexec_fn, rather than just calling
    setuid and setgid. This will change the ids for that subprocess only"""

    def set_ids():
        if user:
            user_info = pwd.getpwnam(user)
            os.setgid(user_info.pw_gid)
            os.setuid(user_info.pw_uid)

    return set_ids


class RsyncService(Service):

    def __rsync_worker(self, line, user, job):
        proc_stdout = tempfile.TemporaryFile(mode='w+b', buffering=0)
        try:
            rsync_proc = subprocess.Popen(
                line,
                shell=True,
                stdout=proc_stdout.fileno(),
                stderr=subprocess.PIPE,
                bufsize=0,
                preexec_fn=demote(user)
            )
            seek = 0
            old_seek = 0
            progress = 0
            message = 'Starting rsync copy job...'
            while rsync_proc.poll() is None:
                job.set_progress(progress, message)
                proc_op = ''
                proc_stdout.seek(seek)
                try:
                    while True:
                        op_byte = proc_stdout.read(1).decode('utf8')
                        if op_byte == '':
                            # In this case break before incrementing `seek`
                            break
                        seek += 1
                        if op_byte == '\r':
                            break
                        proc_op += op_byte
                        seek += 1
                    if old_seek != seek:
                        old_seek = seek
                        message = proc_op.strip()
                        try:
                            progress = int([x for x in message.split(' ') if '%' in x][0][:-1])
                        except (IndexError, ValueError):
                            pass
                except BaseException as err:
                    # Catch IOERROR Errno 9 which usually arises because
                    # of already closed fileobject being used here therby
                    # raising Bad File Descriptor error. In this case break
                    # and the outer while loop will check for rsync_proc.poll()
                    # to be None or not and DTRT
                    if hasattr(err, 'errno') and err.errno == 9:
                        break
                    logger.debug('Error whilst parsing rsync progress', exc_info=True)

        except BaseException as e:
            raise CallError(f'Rsync copy job id: {job.id} failed due to: {e}', errno.EIO)

        if rsync_proc.returncode != 0:
            job.set_progress(None, 'Rsync copy job failed')
            raise CallError(
                f'Rsync copy job id: {job.id} returned non-zero exit code. Command used was: {line}. Error: {rsync_proc.stderr.read()}'
            )

    @accepts(Dict(
        'rsync-copy',
        Str('user', required=True),
        Str('path', required=True),
        Str('remote_user'),
        Str('remote_host', required=True),
        Str('remote_path'),
        Int('remote_ssh_port'),
        Str('remote_module'),
        Str('direction', enum=['PUSH', 'PULL'], required=True),
        Str('mode', enum=['MODULE', 'SSH'], required=True),
        Str('remote_password'),
        Dict(
            'properties',
            Bool('recursive'),
            Bool('compress'),
            Bool('times'),
            Bool('archive'),
            Bool('delete'),
            Bool('preserve_permissions'),
            Bool('preserve_attributes'),
            Bool('delay_updates')
        ),
        required=True
    ))
    @job()
    def copy(self, job, rcopy):
        """
        Starts an rsync copy task between current freenas machine
        and specified remote host (or local copy too). It reports
        the progress of the copy task.
        """

        # Assigning variables and such
        user = rcopy.get('user')
        path = rcopy.get('path')
        mode = rcopy.get('mode')
        remote_path = rcopy.get('remote_path')
        remote_host = rcopy.get('remote_host')
        remote_module = rcopy.get('remote_module')
        remote_user = rcopy.get('remote_user', rcopy.get('user'))
        remote_address = remote_host if '@' in remote_host else f'"{remote_user}"@{remote_host}'
        remote_password = rcopy.get('remote_password', None)
        password_file = None
        properties = rcopy.get('properties', defaultdict(bool))

        # Let's do a brief check of all the user provided parameters
        if not path:
            raise ValueError('The path is required')
        elif not os.path.exists(path):
            raise CallError(f'The specified path: {path} does not exist', errno.ENOENT)

        if not remote_host:
            raise ValueError('The remote host is required')

        if mode == 'SSH' and not remote_path:
            raise ValueError('The remote path is required')
        elif mode == 'MODULE' and not remote_module:
            raise ValueError('The remote module is required')

        try:
            pwd.getpwnam(user)
        except KeyError:
            raise CallError(f'User: {user} does not exist', errno.ENOENT)
        if (
            mode == 'SSH' and
            rcopy.get('remote_host') in ['127.0.0.1', 'localhost'] and
            not os.path.exists(remote_path)
        ):
            raise CallError(f'The specified path: {remote_path} does not exist', errno.ENOENT)

        # Phew! with that out of the let's begin the transfer

        line = f'{RSYNC_PATH} --info=progress2 -h'
        if properties:
            if properties.get('recursive'):
                line += ' -r'
            if properties.get('times'):
                line += ' -t'
            if properties.get('compress'):
                line += ' -z'
            if properties.get('archive'):
                line += ' -a'
            if properties.get('preserve_permissions'):
                line += ' -p'
            if properties.get('preserve_attributes'):
                line += ' -X'
            if properties.get('delete'):
                line += ' --delete-delay'
            if properties.get('delay_updates'):
                line += ' --delay-updates'

        if mode == 'MODULE':
            if rcopy.get('direction') == 'PUSH':
                line += f' "{path}" {remote_address}::"{remote_module}"'
            else:
                line += f' {remote_address}::"{remote_module}" "{path}"'
            if remote_password:
                password_file = tempfile.NamedTemporaryFile(mode='w')

                password_file.write(remote_password)
                password_file.flush()
                shutil.chown(password_file.name, user=user)
                os.chmod(password_file.name, 0o600)
                line += f' --password-file={password_file.name}'
        else:
            # there seems to be some code duplication here but hey its simple
            # if you find a way (THAT DOES NOT BREAK localhost based rsync copies)
            # then please go for it
            if rcopy.get('remote_host') in ['127.0.0.1', 'localhost']:
                if rcopy['direction'] == 'PUSH':
                    line += f' "{path}" "{remote_path}"'
                else:
                    line += f' "{remote_path}" "{path}"'
            else:
                line += ' -e "ssh -p {0} -o BatchMode=yes -o StrictHostKeyChecking=yes"'.format(
                    rcopy.get('remote_ssh_port', 22)
                )
                if rcopy['direction'] == 'PUSH':
                    line += f' "{path}" {remote_address}:\\""{remote_path}"\\"'
                else:
                    line += f' {remote_address}:\\""{remote_path}"\\" "{path}"'

        logger.debug(f'Executing rsync job id: {job.id} with the following command {line}')
        try:
            t = threading.Thread(target=self.__rsync_worker, args=(line, user, job), daemon=True)
            t.start()
            t.join()
        finally:
            if password_file:
                password_file.close()

        job.set_progress(100, 'Rsync copy job successfully completed')


class RsyncdService(SystemServiceService):

    class Config:
        service = "rsync"
        service_model = 'rsyncd'
        datastore_prefix = "rsyncd_"

    @accepts(Dict(
        'rsyncd_update',
        Int('port', validators=[Range(min=1, max=65535)]),
        Str('auxiliary')
    ))
    async def update(self, data):
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
        'rsyncmod',
        Str('name'),
        Str('comment'),
        Str('path'),
        Str('mode'),
        Int('maxconn'),
        Str('user'),
        Str('group'),
        List('hostsallow', items=[Str('hostsallow')]),
        List('hostsdeny', items=[Str('hostdeny')]),
        Str('auxiliary'),
        register=True,
    ))
    async def do_create(self, data):
        if re.search(r'[/\]]', data.get('name')):
            raise ValidationError(
                "name",
                "The name cannot contain slash or a closing square backet."
            )

        if data.get("hostsallow"):
            data["hostsallow"] = " ".join(data["hostsallow"])
        else:
            data["hostsallow"] = ''

        if data.get("hostsdeny"):
            data["hostsdeny"] = " ".join(data["hostsdeny"])
        else:
            data["hostsdeny"] = ''

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )
        await self.middleware.call('service.reload', 'rsync')
        return data

    @accepts(Int('id'), Ref('rsyncmod'))
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

        if re.search(r'[/\]]', module['name']):
            raise ValidationError(
                "name",
                "The name cannot contain slash or a closing square backet."
            )

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            data,
            {'prefix': self._config.datastore_prefix}
        )
        await self.middleware.call('service.reload', 'rsync')

        return module

    @accepts(Int('id'))
    async def do_delete(self, id):
        return await self.middleware.call('datastore.delete', self._config.datastore, id)
