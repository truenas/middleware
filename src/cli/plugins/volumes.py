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
from namespace import Namespace, EntityNamespace, IndexCommand, Command, CommandException, description
from output import Column, output_msg, output_table, output_tree
from utils import first_or_default


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


@description("Finds volumes available to import")
class FindVolumesCommand(Command):
    def run(self, context, args, kwargs, opargs):
        vols = context.connection.call_sync('volumes.find')
        output_table(vols, [
            Column('ID', '/id'),
            Column('Volume name', '/name'),
            Column('Status', '/status')
        ])


@description("Imports given volume")
class ImportVolumeCommand(Command):
    def run(self, context, args, kwargs, opargs):
        if len(args) < 1:
            raise CommandException('Not enough arguments passed')

        id = args[0]
        oldname = args[0]

        if not args[0].isdigit():
            vols = context.connection.call_sync('volumes.find')
            vol = first_or_default(lambda v: v['name'] == args[0], vols)
            if not vol:
                raise CommandException('Importable volume {0} not found'.format(args[0]))

            id = vol['id']
            oldname = vol['name']

        context.submit_task('volume.import', id, kwargs.get('newname', oldname))


@description("Detaches given volume")
class DetachVolumeCommand(Command):
    def run(self, context, args, kwargs, opargs):
        if len(args) < 1:
            raise CommandException('Not enough arguments passed')

        context.submit_task('volume.detach', args[0])


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


@description("Datasets")
class DatasetsNamespace(EntityNamespace):
    def __init__(self, name, context, parent):
        super(DatasetsNamespace, self).__init__(name, context)
        self.parent = parent
        self.path = name
        self.add_property(
            descr='Name',
            name='name',
            get='/name',
            list=True)

        self.add_property(
            descr='Used',
            name='used',
            get='/properties/used/value',
            set=None,
            list=True)

        self.add_property(
            descr='Available',
            name='available',
            get='/properties/avail/value',
            set=None,
            list=True)

        self.add_property(
            descr='Mountpoint',
            name='mountpoint',
            get='/properties/mountpoint/value',
            set=None,
            list=True)

        self.primary_key = self.get_mapping('name')
        self.entity_namespaces = lambda this: [
            PropertiesNamespace('properties', context, this)
        ]

    def query(self, params):
        self.parent.load()
        return self.parent.entity['datasets']

    def get_one(self, name):
        self.parent.load()
        return first_or_default(lambda d: d['name'] == name, self.parent.entity['datasets'])

    def delete(self, name):
        self.context.submit_task('volume.dataset.delete', self.parent.entity['name'], name)

    def save(self, entity, diff, new=False):
        if new:
            self.context.submit_task('volume.dataset.create', self.parent.entity['name'], entity['name'])
            return


@description("Properties")
class PropertiesNamespace(EntityNamespace):
    def __init__(self, name, context, parent):
        super(PropertiesNamespace, self).__init__(name, context)
        self.parent = parent

        self.add_property(
            descr='Property name',
            name='name',
            get='/name',
            list=True)

        self.add_property(
            descr='Value',
            name='value',
            get='/value',
            set=None,
            list=True)

        self.add_property(
            descr='Source',
            name='source',
            get='/source',
            set=None,
            list=True)

    def query(self, params):
        return self.parent.entity['properties']

    def get_one(self, name):
        return first_or_default(lambda d: d['name'] == name, self.parent.entity['properties'])

    def delete(self, name):
        self.context.submit_task('volume.dataset.delete', self.parent.entity['name'], name)

    def save(self, entity, diff, new=False):
        if new:
            self.context.submit_task('volume.dataset.create', self.parent.entity['name'], entity['name'])
            return


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
        self.extra_commands = {
            'find': FindVolumesCommand(),
            'import': ImportVolumeCommand(),
            'detach': DetachVolumeCommand()
        }

        self.entity_commands = lambda vol: {
            'show-topology': ShowTopologyCommand(self, vol),
            'show-disks': ShowDisksCommand(self, vol),
            'scrub': ScrubCommand(vol)
        }

        self.entity_namespaces = lambda this: [
            DatasetsNamespace('datasets', self.context, this),
            PropertiesNamespace('properties', self.context, this)
        ]

    def query(self, params):
        return self.context.connection.call_sync('volumes.query', params)

    def get_one(self, name):
        return self.context.connection.call_sync(
            'volumes.query',
            [('name', '=', name)],
            {'single': True}
        )

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