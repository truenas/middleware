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
from output import output_msg, output_table, output_tree


class VolumeCreateNamespace(Namespace):
    pass


@description("Creates new volume in simple way")
class VolumeCreateCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
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

    def run(self, context, args, kwargs, opargs):
        def print_vdev(vdev):
            if vdev['type'] == 'disk':
                return '{0} (disk)'.format(vdev['path'])
            else:
                return vdev['type']

        volume = self.parent.get_one(self.name)
        tree = filter(lambda x: len(x['children']) > 0, map(lambda (k, v): {'type': k, 'children': v}, volume['topology'].items()))
        output_tree(tree, '/children', print_vdev)


@description("Shows volume disks status")
class ShowDisksCommand(Command):
    def __init__(self, parent, name):
        self.parent = parent
        self.name = name

    def run(self, context, args, kwargs, opargs):
        volume = self.parent.get_one(self.name)
        result = []

        for i in iterate_vdevs(volume['topology']):
            disk = context.connection.call_sync('disk.query', [('name', '=', i['path'])])
            result.append({
                'name': i['path'],
                'status': i['status'],
                'size': disk['mediasize'],
                'serial': disk['serial']
            })

        output_table(result, [
            ('Name', '/path'),
            ('Status', '/status')
        ])

@description("Shows volume disks status")
class ShowDisksCommand(Command):
    def __init__(self, parent, name):
        self.parent = parent
        self.name = name

    def run(self, context, args, kwargs, opargs):
        volume = self.parent.get_one(self.name)
        result = list(iterate_vdevs(volume['topology']))
        output_table(result, [
            ('Name', '/path'),
            ('Status', '/status')
        ])


@description("Scrubs volume")
class ScrubCommand(Command):
    def __init__(self, name):
        self.name = name

    def run(self, context, args, kwargs, opargs):
        context.submit_task('zfs.pool.scrub', self.name)


class DatasetsNamespace(EntityNamespace):
    def __init__(self, volume, path, context):
        super(DatasetsNamespace, self).__init__(path, context)
        self.add_property(
            descr='Name',
            name='name',
            get='/name',
            list=True)

        self.add_property(
            descr='Used',
            name='status',
            get='/status',
            set=None,
            list=True)

        self.add_property(
            descr='Available',
            name='mountpoint',
            get='/mountpoint',
            list=True)

        self.add_property(
            descr='Compression',
            name='mountpoint',
            get='/mountpoint',
            list=True)

        self.add_property(
            descr='Compression ratio',
            name='mountpoint',
            get='/mountpoint',
            list=True)

        self.primary_key = self.get_mapping('name')


@description("Volumes namespace")
class VolumesNamespace(EntityNamespace):
    class ShowTopologyCommand(Command):
        def run(self, context, args, kwargs, opargs):
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
            'show-disks': ShowDisksCommand(self, vol),
            'scrub': ScrubCommand(vol)
        }

        self.entity_namespaces = lambda vol: [
            DatasetsNamespace(vol, vol, context)
        ]

    def query(self, params):
        return self.context.connection.call_sync('volumes.query', params)

    def get_one(self, name):
        return self.context.connection.call_sync('volumes.query', [('name', '=', name)])[0]

    def delete(self, name):
        self.context.submit_task('volume.destroy', name)


def iterate_vdevs(topology):
    for group in topology.values():
        for vdev in group:
            if vdev['type'] == 'disk':
                yield vdev
            elif 'children' in vdev:
                for subvdev in vdev['children']:
                    yield subvdev


def _init(context):
    context.attach_namespace('/', VolumesNamespace('volumes', context))