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
from dispatcher.rpc import RpcException, description, accepts, returns
from dispatcher.rpc import SchemaHelper as h
from task import Provider, Task


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


class DownloadFileTask(Task):
    def verify(self, path):
        pass

    def run(self, path):
        pass


class UploadFileTask(Task):
    def verify(self, dest_path):
        pass

    def run(self, dest_path):
        pass


def _init(dispatcher):
    dispatcher.register_provider('filesystem', FilesystemProvider)
