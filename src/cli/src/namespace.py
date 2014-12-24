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


import collections
from texttable import Texttable
from jsonpointer import resolve_pointer, set_pointer
from output import Column, ValueType, output_dict, output_table, output_msg, output_is_ascii


def description(descr):
    def wrapped(fn):
        fn.description = descr
        return fn

    return wrapped


class Namespace(object):
    def __init__(self, name):
        self.name = name
        self.nslist = []

    def help(self):
        pass

    def get_name(self):
        return self.name

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
        return True

    def register_namespace(self, ns):
        self.nslist.append(ns)


class Command(object):
    def run(self, context, args, kwargs):
        pass

    def complete(self, context, tokens):
        return []


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

        for ns in sorted(nss):
            table.add_row([ns.get_name(), ns.description])

        for name in sorted(cmds.keys()):
            table.add_row([name, cmds[name].description])

        print table.draw()


class RootNamespace(Namespace):
    pass


class EntityNamespace(Namespace):
    def __init__(self, name, context):
        super(EntityNamespace, self).__init__(name)
        self.context = context
        self.property_mappings = []
        self.primary_key = None
        self.entity_commands = None
        self.allow_edit = True
        self.allow_create = True
        self.create_command = self.CreateEntityCommand
        self.delete_command = self.DeleteEntityCommand

    class PropertyMapping(object):
        def __init__(self, name, descr, get, set=None, list=False, type=ValueType.STRING):
            self.name = name
            self.descr = descr
            self.get = get
            self.set = set or get
            self.list = list
            self.type = type

        def do_get(self, obj):
            if callable(self.get):
                return self.get(obj)

            return resolve_pointer(obj, self.get)

        def do_set(self, obj, value):
            if callable(self.set):
                self.set(obj, value)
                return

            set_pointer(obj, self.set, value)

    class SingleItemNamespace(Namespace):
        def __init__(self, name, parent):
            super(EntityNamespace.SingleItemNamespace, self).__init__(name)
            self.name = name
            self.description = name
            self.parent = parent
            self.entity = None
            self.modified = False
            self.nslist = {}

        def on_enter(self):
            self.load_entity()

        def on_leave(self):
            if self.modified:
                output_msg('Object was modified. Type either "save" or "discard" to leave')
                return False

            return True

        def get_name(self):
            return self.parent.primary_key.do_get(self.entity) if self.entity else self.name

        def load_entity(self):
            self.entity = self.parent.get_one(self.name)
            self.modified = False

        def commands(self):
            base = {
                '?': IndexCommand(self),
                'get': self.parent.GetEntityCommand(self),
                'show': self.parent.ShowEntityCommand(self),
            }

            if self.parent.allow_edit:
                base.update({
                    'set': self.parent.SetEntityCommand(self),
                    'save': self.parent.SaveEntityCommand(self),
                    'discard': self.parent.DiscardEntityCommand(self)
                })

            if self.parent.entity_commands is not None:
                base.update(self.parent.entity_commands(self.name))

            return base

    @description("Lists items")
    class ListCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs):
            cols = []
            for col in filter(lambda x: x.list, self.parent.property_mappings):
                cols.append(Column(col.descr, col.get, col.type))

            output_table(self.parent.query(), cols)

    @description("Shows single item")
    class ShowEntityCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs):
            if len(args) != 0:
                pass

            values = collections.OrderedDict()
            entity = self.parent.entity

            for mapping in self.parent.parent.property_mappings:
                if not mapping.get:
                    continue

                values[mapping.descr if output_is_ascii() else mapping.name] = mapping.do_get(entity)

            output_dict(values)

    @description("Prints single item value")
    class GetEntityCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs):
            if not self.parent.parent.has_property(args[0]):
                output_msg('Property {0} not found'.format(args[0]))
                return

            entity = self.parent.entity
            output_msg(self.parent.parent.get_property(args[0], entity))

    @description("Sets single item property")
    class SetEntityCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs):
            for k, v in kwargs.items():
                if not self.parent.parent.has_property(k):
                    output_msg('Property {0} not found'.format(k))
                    return

            entity = self.parent.entity

            for k, v in kwargs.items():
                prop = self.parent.parent.get_mapping(k)
                prop.do_set(entity, v)

            self.parent.modified = True

    @description("Saves item")
    class SaveEntityCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs):
            self.parent.parent.save(self.parent.entity)

    @description("Discards modified item")
    class DiscardEntityCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs):
            self.parent.load_entity()

    @description("Creates new item")
    class CreateEntityCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs):
            entity = {}

            if len(args) > 0:
                prop = self.parent.primary_key
                prop.do_set(entity, args.pop(0))

            for k, v in kwargs.items():
                if not self.parent.has_property(k):
                    output_msg('Property {0} not found'.format(k))
                    return

            for k, v in kwargs.items():
                prop = self.parent.get_mapping(k)
                prop.do_set(entity, v)

            self.parent.save(entity, new=True)

        def complete(self, context, tokens):
            return [x.name + '=' for x in self.parent.property_mappings]

    @description("Removes item")
    class DeleteEntityCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs):
            self.parent.delete(args[0])

    def has_property(self, prop):
        return any(filter(lambda x: x.name == prop, self.property_mappings))

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
        base = {
            '?': IndexCommand(self),
            'list': self.ListCommand(self)
        }

        if self.allow_create:
            base.update({
                'create': self.create_command(self),
                'delete': self.delete_command(self)
            })

        return base

    def namespaces(self):
        if self.primary_key is None:
            return

        for i in self.query():
            name = self.primary_key.do_get(i)
            yield self.SingleItemNamespace(name, self)
