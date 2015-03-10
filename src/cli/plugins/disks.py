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


import os
from namespace import Namespace, EntityNamespace, Command, RpcBasedLoadMixin, description
from output import ValueType, output_msg, output_table


@description("Provides information about installed disks")
class DisksNamespace(RpcBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(DisksNamespace, self).__init__(name, context)

        self.query_call = 'disks.query'

        self.add_property(
            descr='Disk name',
            name='name',
            get=lambda row: os.path.basename(row['path']),
            set=None,
            list=True)

        self.add_property(
            descr='Size',
            name='mediasize',
            get='/mediasize',
            set=None,
            list=True,
            type=ValueType.SIZE)

        self.add_property(
            descr='Online',
            name='builtin',
            get='/online',
            set=None,
            list=True,
            type=ValueType.BOOLEAN)

        self.add_property(
            descr='Disposition',
            name='disposition',
            get=self.get_disposition,
            set=None,
            list=True
        )

        self.primary_key = self.get_mapping('name')
        self.allow_create = False
        self.entity_commands = lambda this: {
            'format': FormatDiskCommand(this),
            'erase': EraseDiskCommand(this)
        }

    def get_one(self, name):
        return self.context.connection.call_sync(
            self.query_call,
            [('path', '=', os.path.join('/dev', name))],
            {'single': True})

    def get_disposition(self, entity):
        return ''


@description("Formats given disk")
class FormatDiskCommand(Command):
    def __init__(self, parent):
        self.disk = parent.entity

    def run(self, context, args, kwargs, opargs):
        fstype = kwargs.pop('fstype', 'freebsd-zfs')
        swapsize = kwargs.pop('swapsize', '2048M')
        context.submit_task('disk.format.gpt', self.disk['path'], fstype)


@description("Erases all data on disk safely")
class EraseDiskCommand(Command):
    def __init__(self, parent):
        pass



def _init(context):
    context.attach_namespace('/', DisksNamespace('disks', context))