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
import json
import config
import time
import natural.date
import gettext
from threading import Lock
from xml.etree import ElementTree
from texttable import Texttable
from jsonpointer import resolve_pointer


output_lock = Lock()
t = gettext.translation('freenas-cli', fallback=True)
_ = t.ugettext


class JsonOutputFormatter(object):
    @staticmethod
    def output_value(value):
        print json.dumps(value)

    @staticmethod
    def output_list(data, label):
        print json.dumps(list(data), indent=4)

    @staticmethod
    def output_dict(data, key_label, value_label):
        print json.dumps(dict(data), indent=4)

    @staticmethod
    def output_table(data, columns):
        print json.dumps(list(data), indent=4)


class AsciiOutputFormatter(object):
    @staticmethod
    def output_value(value):
        print value

    @staticmethod
    def output_list(data, label):
        table = Texttable(max_width=get_terminal_size()[1])
        table.set_deco(Texttable.BORDER | Texttable.VLINES | Texttable.HEADER)
        table.header([label])
        table.add_rows([[i] for i in data])
        print table.draw()

    @staticmethod
    def output_dict(data, key_label, value_label):
        table = Texttable(max_width=get_terminal_size()[1])
        table.set_deco(Texttable.BORDER | Texttable.VLINES | Texttable.HEADER)
        table.header([key_label, value_label])
        table.add_rows([[row[0], row[1]] for row in data.items()], False)
        print table.draw()

    @staticmethod
    def output_table(data, columns):
        table = Texttable(max_width=get_terminal_size()[1])
        table.set_deco(Texttable.BORDER | Texttable.VLINES | Texttable.HEADER)
        table.header([i[0] for i in columns])
        table.add_rows([[resolve_cell(row, i[1]) for i in columns] for row in data], False)
        print table.draw()


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
        return resolve_pointer(row, spec)

    if callable(spec):
        return spec(row)

    return '<unknown>'


def output_value(value, fmt=None):
    if fmt is None:
        fmt = config.instance.variables.get('output-format')

    globals()['{0}OutputFormatter'.format(fmt.title())].output_value(value)


def output_list(data, label='Items', fmt=None):
    if fmt is None:
        fmt = config.instance.variables.get('output-format')

    globals()['{0}OutputFormatter'.format(fmt.title())].output_list(data, label)


def output_dict(data, key_label='Key', value_label='Value', fmt=None):
    if fmt is None:
        fmt = config.instance.variables.get('output-format')

    globals()['{0}OutputFormatter'.format(fmt.title())].output_dict(data, key_label, value_label)


def output_table(data, columns, fmt=None):
    if fmt is None:
        fmt = config.instance.variables.get('output-format')

    globals()['{0}OutputFormatter'.format(fmt.title())].output_table(data, columns)


def output_msg(message, fmt=None):
    print message


def output_is_ascii():
    return config.instance.variables.get('output-format') == 'ascii'


def format_datetime(timestamp):
    fmt = config.instance.variables.get('datetime-format')
    if timestamp is None:
        return _("none")

    if fmt == 'natural':
        return natural.date.duration(timestamp)

    return time.strftime(fmt, time.localtime(timestamp))