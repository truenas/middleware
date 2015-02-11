# +
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


import copy
import collections
from texttable import Texttable
from jsonpointer import resolve_pointer, set_pointer, JsonPointerException
from output import (Column, ValueType, output_dict, output_table,
                    output_msg, output_is_ascii, read_value, format_value)


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
            'help': IndexCommand(self),
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
    def run(self, context, args, kwargs, opargs):
        raise NotImplementedError()

    def complete(self, context, tokens):
        return []


class CommandException(Exception):
    pass


@description("Provides list of commands in this namespace")
class IndexCommand(Command):
    def __init__(self, target):
        self.target = target

    def run(self, context, args, kwargs, opargs):
        # btable corresponds to built-in commands
        btable = Texttable()
        btable.set_deco(Texttable.HEADER | Texttable.VLINES | Texttable.BORDER)
        btable.add_rows([['Builtin Global Commands', 'Description']],
                        header=True)
        for name, cmd in context.ml.builtin_commands.items():
            btable.add_row([name, cmd.description])

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
        print btable.draw()


class RootNamespace(Namespace):
    pass


class PropertyMapping(object):
    def __init__(self, name, descr, get,
                 set=None, list=False, type=ValueType.STRING):
        self.name = name
        self.descr = descr
        self.get = get
        self.set = set or get
        self.list = list
        self.type = type

    def do_get(self, obj):
        if callable(self.get):
            return self.get(obj)

        try:
            return resolve_pointer(obj, self.get)
        except JsonPointerException:
            return None

    def do_set(self, obj, value):
        value = read_value(value, self.type)
        if callable(self.set):
            self.set(obj, value)
            return

        set_pointer(obj, self.set, value)

    def do_append(self, obj, value):
        if self.type != ValueType.ARRAY:
            raise ValueError('Property is not an array')

        value = read_value(value, self.type)
        self.set(obj, self.get(obj).append(value))

    def do_remove(self, obj, value):
        if self.type != ValueType.ARRAY:
            raise ValueError('Property is not an array')

        value = read_value(value, self.type)


class ItemNamespace(Namespace):
    @description("Shows single item")
    class ShowEntityCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs, opargs):
            if len(args) != 0:
                output_msg('Wrong arguments count')
                return

            values = collections.OrderedDict()
            entity = self.parent.entity

            for mapping in self.parent.property_mappings:
                if not mapping.get:
                    continue

                values[mapping.descr if output_is_ascii() else mapping.name] = format_value(mapping.do_get(entity), mapping.type)

            output_dict(values)

    @description("Prints single item value")
    class GetEntityCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs, opargs):
            if len(args) < 1:
                output_msg('Wrong arguments count')
                return

            if not self.parent.has_property(args[0]):
                output_msg('Property {0} not found'.format(args[0]))
                return

            entity = self.parent.entity
            output_msg(self.parent.get_property(args[0], entity))

        def complete(self, context, tokens):
            return [x.name for x in self.parent.property_mappings]

    @description("Sets single item property")
    class SetEntityCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs, opargs):
            for k, v in kwargs.items():
                if not self.parent.has_property(k):
                    output_msg('Property {0} not found'.format(k))
                    return

            entity = self.parent.entity

            for k, v in kwargs.items():
                prop = self.parent.get_mapping(k)
                prop.do_set(entity, v)

            for k, op, v in opargs:
                if op not in ('+=', '-='):
                    raise CommandException(
                        "Syntax error, invalid operator used")

                prop = self.parent.get_mapping(k)

                if op == '+=':
                    prop.do_append(entity, v)

                if op == '-=':
                    prop.do_remove(entity, v)

            self.parent.modified = True

        def complete(self, context, tokens):
            return [x.name + '=' for x in self.parent.property_mappings]

    @description("Saves item")
    class SaveEntityCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs, opargs):
            self.parent.save()
            self.parent.modified = False

    @description("Discards modified item")
    class DiscardEntityCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs, opargs):
            self.parent.load()
            self.parent.modified = False

    def __init__(self, name):
        super(ItemNamespace, self).__init__(name)
        self.name = name
        self.description = name
        self.entity = None
        self.orig_entity = None
        self.allow_edit = True
        self.modified = False
        self.property_mappings = []
        self.subcommands = {}
        self.nslist = []

    def on_enter(self):
        self.load()

    def on_leave(self):
        if self.modified:
            output_msg('Object was modified.'
                       ' Type either "save" or "discard" to leave')
            return False

        return True

    def get_name(self):
        return self.name

    def get_changed_keys(self):
        for i in self.entity.keys():
            if i not in self.orig_entity.keys():
                yield i
                continue

            if self.entity[i] != self.orig_entity[i]:
                yield i

    def get_diff(self):
        return {k: self.entity[k] for k in self.get_changed_keys()}

    def load(self):
        raise NotImplementedError()

    def save(self):
        raise NotImplementedError()

    def has_property(self, prop):
        return any(filter(lambda x: x.name == prop, self.property_mappings))

    def get_mapping(self, prop):
        return filter(lambda x: x.name == prop, self.property_mappings)[0]

    def add_property(self, **kwargs):
        self.property_mappings.append(PropertyMapping(**kwargs))

    def get_property(self, prop, obj):
        mapping = self.get_mapping(prop)
        return mapping.do_get(obj)

    def commands(self):
        base = {
            '?': IndexCommand(self),
            'get': self.GetEntityCommand(self),
            'show': self.ShowEntityCommand(self),
        }

        if self.allow_edit:
            base.update({
                'set': self.SetEntityCommand(self),
                'save': self.SaveEntityCommand(self),
                'discard': self.DiscardEntityCommand(self)
            })

        if self.commands is not None:
            base.update(self.subcommands)

        return base


class ConfigNamespace(ItemNamespace):
    def __init__(self, name, context):
        super(ConfigNamespace, self).__init__(name)
        self.context = context
        self.property_mappings = []


class EntityNamespace(Namespace):
    class SingleItemNamespace(ItemNamespace):
        def __init__(self, name, parent):
            super(EntityNamespace.SingleItemNamespace, self).__init__(name)
            self.parent = parent
            self.property_mappings = parent.property_mappings

            if parent.entity_commands:
                self.subcommands = parent.entity_commands(name)

            if parent.entity_namespaces:
                self.nslist = parent.entity_namespaces(self)

        def get_name(self):
            return self.parent.primary_key.do_get(self.entity) if self.entity else self.name

        def load(self):
            self.entity = self.parent.get_one(self.name)
            self.orig_entity = copy.deepcopy(self.entity)

        def save(self):
            self.parent.save(self.entity, self.get_diff())
            self.modified = False

    def __init__(self, name, context):
        super(EntityNamespace, self).__init__(name)
        self.context = context
        self.property_mappings = []
        self.primary_key = None
        self.extra_commands = None
        self.entity_commands = None
        self.entity_namespaces = None
        self.allow_edit = True
        self.allow_create = True
        self.skeleton_entity = {}
        self.create_command = self.CreateEntityCommand
        self.delete_command = self.DeleteEntityCommand

    @description("Lists items")
    class ListCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs, opargs):
            cols = []
            params = []

            for k, v in kwargs.items():
                prop = self.parent.get_mapping(k)
                v = read_value(v, prop.type)
                params.append((k, '=', v))

            for k, op, v in opargs:
                prop = self.parent.get_mapping(k)
                v = read_value(v, prop.type)
                params.append((k, '~' if op == '~=' else op, v))

            for col in filter(lambda x: x.list, self.parent.property_mappings):
                cols.append(Column(col.descr, col.get, col.type))

            output_table(self.parent.query(params), cols)

    @description("Creates new item")
    class CreateEntityCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs, opargs):
            entity = copy.deepcopy(self.parent.skeleton_entity)

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

            self.parent.save(entity, entity, new=True)

        def complete(self, context, tokens):
            return [x.name + '=' for x in self.parent.property_mappings]

    @description("Removes item")
    class DeleteEntityCommand(Command):
        def __init__(self, parent):
            self.parent = parent

        def run(self, context, args, kwargs, opargs):
            self.parent.delete(args[0])

    def has_property(self, prop):
        return any(filter(lambda x: x.name == prop, self.property_mappings))

    def get_mapping(self, prop):
        return filter(lambda x: x.name == prop, self.property_mappings)[0]

    def get_property(self, prop, obj):
        mapping = self.get_mapping(prop)
        return mapping.do_get(obj)

    def get_one(self, name):
        raise NotImplementedError()

    def update_entity(self, name):
        raise NotImplementedError()

    def query(self, params):
        raise NotImplementedError()

    def add_property(self, **kwargs):
        self.property_mappings.append(PropertyMapping(**kwargs))

    def commands(self):
        base = {
            '?': IndexCommand(self),
            'list': self.ListCommand(self)
        }

        if self.extra_commands:
            base.update(self.extra_commands)

        if self.allow_create:
            base.update({
                'create': self.create_command(self),
                'delete': self.delete_command(self)
            })

        return base

    def namespaces(self):
        if self.primary_key is None:
            return

        for i in self.query([]):
            name = self.primary_key.do_get(i)
            yield self.SingleItemNamespace(name, self)
