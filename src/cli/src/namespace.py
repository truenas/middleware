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

from texttable import Texttable
from jsonpointer import resolve_pointer, set_pointer
from output import output_dict, output_table, output_msg


def description(descr):
    def wrapped(fn):
        fn.description = descr
        return fn

    return wrapped


class Namespace(object):
    def __init__(self):
        self.nslist = {}

    def help(self):
        pass

    def commands(self):
        return {
            '?': IndexCommand(self),
            'help': IndexCommand(self)
        }

    def namespaces(self):
        return self.nslist

    def on_enter(self):
        pass

    def on_leave(self):
        pass

    def register_namespace(self, name, ns):
        self.nslist[name] = ns


class Command(object):
    def run(self, context, args, kwargs):
        pass


class CommandException(Exception):
    pass


@description("Provides list of commands in this namespace")
class IndexCommand(Command):
    def __init__(self, target):
        self.target = target

    def run(self, context, args, kwargs):
        table = Texttable()
        table.set_deco(Texttable.HEADER | Texttable.VLINES | Texttable.BORDER)
        table.add_rows([['Command', 'Description']], header=True)
        nss = self.target.namespaces()
        cmds = self.target.commands()

        for name in sorted(nss.keys()):
            table.add_row([name, nss[name].description])

        for name in sorted(cmds.keys()):
            table.add_row([name, cmds[name].description])

        print table.draw()


class RootNamespace(Namespace):
    pass


class EntityNamespace(Namespace):
    def __init__(self, context):
        super(EntityNamespace, self).__init__()
        self.context = context
        self.property_mappings = []
        self.primary_key = None
        self.entity_commands = None

    class PropertyMapping(object):
        def __init__(self, name, descr, get, set=None, list=False):
            self.name = name
            self.descr = descr
            self.get = get
            self.set = set if set is not None else get
            self.list = list

        def do_get(self, obj):
            if callable(self.get):
                return self.get(obj)

            return resolve_pointer(obj, self.get)

        def do_set(self, obj, value):
            if callable(self.set):
                self.set(obj, value)

            set_pointer(obj, self.set, value)

    class SingleItemNamespace(Namespace):
        def __init__(self, name, parent):
            super(Namespace, self).__init__()
            self.name = name
            self.description = name
            self.parent = parent
            self.nslist = {}

        def commands(self):
            base = {
                '?': IndexCommand(self),
                'get': self.parent.GetEntityCommand(self.name, self),
                'set': self.parent.SetEntityCommand(self.name, self),
                'show': self.parent.ShowEntityCommand(self.name, self),
                'delete': self.parent.DeleteEntityCommand(self.name, self)
            }

            base.update(self.parent.entity_commands(self.name))

    @description("Lists items")
    class ListCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs):
            cols = []
            for col in filter(lambda x: x.list, self.parent.property_mappings):
                cols.append((col.descr, col.get))

            output_table(self.parent.query(), cols)

    @description("Shows single item")
    class ShowEntityCommand(Command):
        def __init__(self, name, parent):
            self.name = name
            self.parent = parent

        def run(self, context, args, kwargs):
            if len(args) != 0:
                pass

            values = {}
            entity = self.parent.parent.get_one(self.name)

            for mapping in self.parent.parent.property_mappings:
                if not mapping.get:
                    continue

                values[mapping.name] = mapping.do_get(entity)

            output_dict(values)

    @description("Prints single item value")
    class GetEntityCommand(Command):
        def __init__(self, name, parent):
            self.name = name
            self.parent = parent

        def run(self, context, args, kwargs):
            if not self.parent.parent.has_property(args[0]):
                output_msg('Property {0} not found'.format(args[0]))
                return

            entity = self.parent.parent.get_one(self.name)
            output_msg(self.parent.parent.get_property(args[0], entity))

    @description("Sets single item property")
    class SetEntityCommand(Command):
        def __init__(self, name, parent):
            self.name = name
            self.parent = parent

        def run(self, context, args, kwargs):
            for k, v in kwargs.items():
                if not self.parent.parent.has_property(k):
                    output_msg('Property {0} not found'.format(k))
                    return

            entity = self.parent.parent.get_one(self.name)

            for k, v in kwargs.items():
                prop = self.parent.parent.get_mapping(k)
                prop.do_set(entity, v)

            self.parent.parent.save(entity)

    @description("Creates new item")
    class CreateEntityCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs):
            for k, v in kwargs.items():
                if not self.parent.has_property(k):
                    output_msg('Property {0} not found'.format(k))
                    return

            entity = {}

            for k, v in kwargs.items():
                prop = self.parent.get_mapping(k)
                prop.do_set(entity, v)

            self.parent.save(entity, new=True)

    @description("Removes item")
    class DeleteEntityCommand(Command):
        def __init__(self, name, parent):
            self.name = name
            self.parent = parent

    def has_property(self, prop):
        return len(filter(lambda x: x.name == prop, self.property_mappings)) > 0

    def get_mapping(self, prop):
        return filter(lambda x: x.name == prop, self.property_mappings)[0]

    def get_property(self, prop, obj):
        mapping = self.get_mapping(prop)
        return mapping.do_get(obj)

    def get_entity(self, name):
        pass

    def update_entity(self, name):
        pass

    def query(self):
        pass

    def add_property(self, **kwargs):
        self.property_mappings.append(self.PropertyMapping(**kwargs))

    def commands(self):
        return {
            '?': IndexCommand(self),
            'create': self.CreateEntityCommand(self),
            'list': self.ListCommand(self)
        }

    def namespaces(self):
        result = {}

        if self.primary_key is None:
            return result

        for i in self.query():
            name = resolve_pointer(i, self.primary_key)
            result[name] = self.SingleItemNamespace(name, self)

        return result