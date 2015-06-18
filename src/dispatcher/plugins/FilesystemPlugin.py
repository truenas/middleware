#+
# Copyright 2014 iXsystems, Inc.
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


import errno
import os
import stat
from dispatcher.rpc import RpcException, description, accepts, returns, pass_sender, private
from dispatcher.rpc import SchemaHelper as h
from task import Provider, Task, TaskStatus
from auth import FileToken


@description("Provides informations filesystem structure")
class FilesystemProvider(Provider):
    @description("Lists contents of given directory")
    @accepts(str)
    @returns(h.array(h.ref('directory')))
    def list_dir(self, path):
        result = []
        if not os.path.isdir(path):
            raise RpcException(errno.ENOENT, 'Path {0} is not a directory'.format(path))

        for i in os.listdir(path):
            try:
                st = os.stat(os.path.join(path, i))
            except OSError:
                continue

            if stat.S_ISDIR(st.st_mode):
                typ = 'DIRECTORY'
                size = None
            elif stat.S_ISLNK(st.st_mode):
                typ = 'LINK'
                size = None
            else:
                typ = 'FILE'
                size = st.st_size

            item = {
                'name': i,
                'type': typ,
                'modified': st.st_mtime
            }

            if size is not None:
                item['size'] = size

            result.append(item)

        return result

    @pass_sender
    @accepts(str)
    @returns(str)
    def download(self, path, sender):
        try:
            f = open(path, 'r')
        except OSError, e:
            raise RpcException(e.errno, e.message)

        token = self.dispatcher.token_store.issue_token(FileToken(
            user=sender.user,
            lifetime=60,
            direction='download',
            file=f
        ))

        return token

    @pass_sender
    @accepts(str, long, str)
    @returns(str)
    def upload(self, dest_path, size, mode, sender):
        try:
            f = open(dest_path, 'w')
        except OSError, e:
            raise RpcException(e.errno, e.message)

        token = self.dispatcher.token_store.issue_token(FileToken(
            user=sender.user,
            lifetime=60,
            direction='upload',
            file=f,
            size=size
        ))

        return token


@accepts(str)
@private
class DownloadFileTask(Task):
    def verify(self, name, connection):
        return []

    def run(self, connection):
        self.connection = connection
        self.connection.done.wait()

    def get_status(self):
        if not self.connection:
            return TaskStatus(0)

        percentage = (self.connection.bytes_done / self.connection.bytes_total) * 100
        return TaskStatus(percentage)


@accepts(str, long)
@private
class UploadFileTask(Task):
    def verify(self, name, connection):
        return []

    def run(self, connection):
        self.connection = connection
        self.connection.done.wait()

    def get_status(self):
        if not self.connection:
            return TaskStatus(0)

        percentage = (self.connection.bytes_done / self.connection.bytes_total) * 100
        return TaskStatus(percentage)


def _init(dispatcher, plugin):
    plugin.register_provider('filesystem', FilesystemProvider)

    plugin.register_provider('filesystem', FilesystemProvider)
    plugin.register_task_handler('file.download', DownloadFileTask)
    plugin.register_task_handler('file.upload', UploadFileTask)
