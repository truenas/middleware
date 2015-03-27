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
import importlib
import sys
import config
import gettext
import enum
import string
from threading import Lock


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

    if hw[0] == 0 or hw[1] == 0:
        hw = (25, 80)

    return hw


def resolve_cell(row, spec):
    if type(spec) == str:
        return row.get(spec)

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
    return get_formatter(fmt).format_value(value, vt)


def output_value(value, fmt=None):
    fmt = fmt or config.instance.variables.get('output-format')
    return get_formatter(fmt).output_value(value)


def output_list(data, label=_("Items"), fmt=None):
    fmt = fmt or config.instance.variables.get('output-format')
    return get_formatter(fmt).output_list(data, label)


def output_dict(data, key_label=_("Key"), value_label=_("Value"), fmt=None):
    fmt = fmt or config.instance.variables.get('output-format')
    return get_formatter(fmt).output_dict(data, key_label, value_label)


def output_table(data, columns, fmt=None):
    fmt = fmt or config.instance.variables.get('output-format')
    return get_formatter(fmt).output_table(data, columns)


def output_object(*items, **kwargs):
    fmt = kwargs.pop('fmt', None)
    fmt = fmt or config.instance.variables.get('output-format')
    return get_formatter(fmt).output_object(items)


def output_tree(tree, children, label, fmt=None):
    fmt = fmt or config.instance.variables.get('output-format')
    return get_formatter(fmt).output_tree(tree, children, label)


def get_formatter(name):
    module = importlib.import_module('output.' + name)
    return module._formatter()


def output_msg(message, fmt=None, **kwargs):
    fmt = fmt or config.instance.variables.get('output-format')
    return get_formatter(fmt).output_msg(message, **kwargs)


def output_is_ascii():
    return config.instance.variables.get('output-format') == 'ascii'
