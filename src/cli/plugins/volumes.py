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


import time
from namespace import Namespace, EntityNamespace, IndexCommand, Command, description
from output import output_msg, output_table, format_datetime


class VolumeCreateNamespace(Namespace):
    pass


@description("Creates new volume in simple way")
class VolumeCreateCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs):
        name = args.pop(0)
        disks = args

        if 'alldisks' in disks:
            disks = context.connection.call_sync('volumes.get_available_disks')

        context.submit_task('volume.create_auto', name, 'zfs', disks)


@description("Shows volume topology")
class ShowTopologyCommand(Command):
    def __init__(self, parent, name):
        self.parent = parent
        self.name = name

    def __print_vdev(self):
        pass

    def run(self, context, args, kwargs):
        volume = self.parent.get_one(self.name)


@description("Scrubs volume")
class ScrubCommand(Command):
    def __init__(self, name):
        self.name = name

    def run(self, context, args, kwargs):
        context.submit_task('zfs.pool.scrub', self.name)


class DatasetsNamespace(EntityNamespace):
    def __init__(self, volume, path):
        pass


@description("Volumes namespace")
class VolumesNamespace(EntityNamespace):
    class ShowTopologyCommand(Command):
        def run(self, context, args, kwargs):
            pass

    def __init__(self, name, context):
        super(VolumesNamespace, self).__init__(name, context)
        self.create_command = VolumeCreateCommand
        self.add_property(
            descr='Volume name',
            name='name',
            get='/name',
            list=True)

        self.add_property(
            descr='Status',
            name='status',
            get='/status',
            set=None,
            list=True)

        self.add_property(
            descr='Mount point',
            name='mountpoint',
            get='/mountpoint',
            list=True)

        self.primary_key = self.get_mapping('name')
        self.entity_commands = lambda vol: {
            'show-topology': ShowTopologyCommand(self, vol),
            'scrub': ScrubCommand(vol)
        }

    def query(self):
        return self.context.connection.call_sync('volumes.query')

    def get_one(self, name):
        return self.context.connection.call_sync('volumes.query', [('name', '=', name)])[0]

    def delete(self, name):
        self.context.submit_task('volume.destroy', name)


def _init(context):
    context.attach_namespace('/', VolumesNamespace('volumes', context))