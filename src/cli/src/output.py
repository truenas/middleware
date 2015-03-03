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
import sys
import json
import config
import time
import gettext
import enum
import string
import natural.date
import natural.size
from threading import Lock
from xml.etree import ElementTree
from texttable import Texttable
from jsonpointer import resolve_pointer, JsonPointerException


output_lock = Lock()
t = gettext.translation('freenas-cli', fallback=True)
_ = t.ugettext


class ValueType(enum.Enum):
    STRING = 1
    NUMBER = 2
    HEXNUMBER = 3
    BOOLEAN = 4
    SIZE = 5
    TIME = 6
    SET = 7


class Column(object):
    def __init__(self, label, accessor, vt=ValueType.STRING):
        self.label = label
        self.accessor = accessor
        self.vt = vt


class ProgressBar(object):
    def __init__(self):
        self.message = None
        self.percentage = 0
        sys.stdout.write('\n')

    def draw(self):
        progress_width = get_terminal_size()[0] - 5
        filled_width = int(self.percentage * progress_width)
        sys.stdout.write('\033[2K\033[A\033[2K\r')
        sys.stdout.write('Status: {}\n'.format(self.message))
        sys.stdout.write('[{}{}] {:.2%}'.format(
            '#' * filled_width,
            '_' * (progress_width - filled_width),
            self.percentage))

        sys.stdout.flush()

    def update(self, percentage=None, message=None):
        if percentage:
            self.percentage = percentage / 100

        if message:
            self.message = message

        self.draw()

    def finish(self):
        self.percentage = 1
        self.draw()
        sys.stdout.write('\n')


class JsonOutputFormatter(object):
    @staticmethod
    def format_value(value, vt):
        if vt == ValueType.BOOLEAN:
            value = bool(value)

        return json.dumps(value)

    @staticmethod
    def output_list(data, label):
        print json.dumps(list(data), indent=4)

    @staticmethod
    def output_dict(data, key_label, value_label):
        print json.dumps(dict(data), indent=4)

    @staticmethod
    def output_table(data, columns):
        print json.dumps(list(data), indent=4)

    @staticmethod
    def output_tree(data, children, label):
        print json.dumps(list(data), indent=4)


class AsciiOutputFormatter(object):
    @staticmethod
    def format_value(value, vt):
        if vt == ValueType.BOOLEAN:
            return _("yes") if value else _("no")

        if value is None:
            return _("none")

        if vt == ValueType.SET:
            value = list(value)
            if len(value) == 0:
                return _("empty")

            return '\n'.join(value)

        if vt == ValueType.STRING:
            return value

        if vt == ValueType.NUMBER:
            return str(value)

        if vt == ValueType.HEXNUMBER:
            return hex(value)

        if vt == ValueType.SIZE:
            return natural.size.binarysize(value)

        if vt == ValueType.TIME:
            fmt = config.instance.variables.get('datetime-format')
            if fmt == 'natural':
                return natural.date.duration(value)

            return time.strftime(fmt, time.localtime(value))

    @staticmethod
    def output_list(data, label, vt=ValueType.STRING):
        table = Texttable(max_width=get_terminal_size()[1])
        table.set_deco(Texttable.BORDER | Texttable.VLINES | Texttable.HEADER)
        table.header([label])
        table.add_rows([[i] for i in data], False)
        print table.draw()

    @staticmethod
    def output_dict(data, key_label, value_label, value_vt=ValueType.STRING):
        table = Texttable(max_width=get_terminal_size()[1])
        table.set_deco(Texttable.BORDER | Texttable.VLINES | Texttable.HEADER)
        table.header([key_label, value_label])
        table.add_rows([[row[0], AsciiOutputFormatter.format_value(row[1], value_vt)] for row in data.items()], False)
        print table.draw()

    @staticmethod
    def output_table(data, columns):
        table = Texttable(max_width=get_terminal_size()[1])
        table.set_deco(Texttable.BORDER | Texttable.VLINES | Texttable.HEADER)
        table.header([i.label for i in columns])
        table.add_rows([[AsciiOutputFormatter.format_value(resolve_cell(row, i.accessor), i.vt) for i in columns] for row in data], False)
        print table.draw()

    @staticmethod
    def output_object(items):
        table = Texttable(max_width=get_terminal_size()[1])
        table.set_deco(Texttable.BORDER | Texttable.VLINES)
        for i in items:
            if len(i) == 3:
                name, _, value = i
                table.add_row([name, AsciiOutputFormatter.format_value(value, ValueType.STRING)])

            if len(i) == 4:
                name, _, value, vt = i
                table.add_row([name, AsciiOutputFormatter.format_value(value, vt)])

        print table.draw()

    @staticmethod
    def output_tree(tree, children, label, label_vt=ValueType.STRING):
        def branch(obj, indent):
            for idx, i in enumerate(obj):
                subtree = resolve_cell(i, children)
                char = '+' if subtree else ('`' if idx == len(obj) - 1 else '|')
                print '{0} {1}-- {2}'.format('    ' * indent, char, resolve_cell(i, label))
                if subtree:
                    branch(subtree, indent + 1)

        branch(tree, 0)


def get_terminal_size(fd=1):
    """
    Returns height and width of current terminal. First tries to get
    size via termios.TIOCGWINSZ, then from environment. Defaults to 25
    lines x 80 columns if both methods fail.

    :param fd: file descriptor (default: 1=stdout)
    """
    try:
        import fcntl, termios, struct
        hw = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
    except:
        try:
            hw = (os.environ['LINES'], os.environ['COLUMNS'])
        except:
            hw = (25, 80)

    return hw


def resolve_cell(row, spec):
    if type(spec) == str:
        try:
            return resolve_pointer(row, spec)
        except JsonPointerException:
            return None

    if callable(spec):
        return spec(row)

    return '<unknown>'


def read_value(value, tv=ValueType.STRING):
    if tv == ValueType.STRING:
        return str(value)

    if tv == ValueType.NUMBER:
        return int(value)

    if tv == ValueType.BOOLEAN:
        if value in ('true', 'yes', 'YES', '1'):
            return True

        if value in ('false', 'no', 'NO', '0'):
            return False

    if tv == ValueType.SIZE:
        if value[-1] in string.ascii_letters:
            suffix = value[-1]
            value = long(value[:-1])

            if suffix in ('k', 'K', 'kb', 'KB'):
                value *= 1024

            if suffix in ('m', 'M', 'MB', 'mb'):
                value *= 1024 * 1024

            if suffix in ('g', 'G', 'GB', 'gb'):
                value *= 1024 * 1024 * 1024

            if suffix in ('t', 'T', 'TB', 'tb'):
                value *= 1024 * 1024 * 1024 * 1024

        return long(value)

    if tv == ValueType.SET:
        if type(value) is list:
            return value

        return value.split(',')

    raise ValueError('Invalid value')


def format_value(value, vt=ValueType.STRING, fmt=None):
    fmt = fmt or config.instance.variables.get('output-format')
    return globals()['{0}OutputFormatter'.format(fmt.title())].format_value(value, vt)


def output_value(value, fmt=None):
    fmt = fmt or config.instance.variables.get('output-format')
    globals()['{0}OutputFormatter'.format(fmt.title())].output_value(value)


def output_list(data, label=_("Items"), fmt=None):
    fmt = fmt or config.instance.variables.get('output-format')
    globals()['{0}OutputFormatter'.format(fmt.title())].output_list(data, label)


def output_dict(data, key_label=_("Key"), value_label=_("Value"), fmt=None):
    fmt = fmt or config.instance.variables.get('output-format')
    globals()['{0}OutputFormatter'.format(fmt.title())].output_dict(data, key_label, value_label)


def output_table(data, columns, fmt=None):
    fmt = fmt or config.instance.variables.get('output-format')
    globals()['{0}OutputFormatter'.format(fmt.title())].output_table(data, columns)


def output_object(*items, **kwargs):
    fmt = kwargs.pop('fmt', None)
    fmt = fmt or config.instance.variables.get('output-format')
    globals()['{0}OutputFormatter'.format(fmt.title())].output_object(items)


def output_tree(tree, children, label, fmt=None):
    fmt = fmt or config.instance.variables.get('output-format')
    globals()['{0}OutputFormatter'.format(fmt.title())].output_tree(tree, children, label)


def output_msg(message, fmt=None):
    print message


def output_is_ascii():
    return config.instance.variables.get('output-format') == 'ascii'
