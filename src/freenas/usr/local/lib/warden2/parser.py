#!/usr/local/bin/python
#
# Copyright 2015 iXsystems, Inc.
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
import argparse
from boot_set import boot_jail_prop
from chroot import chroot_jail
from create import create_jail
from delete import delete_jail
from list import list_jails
from set import set_jail_prop
from start import start_jail
from stop import stop_jail
from template import template_handling
from warden import warden_usage


# Set up the parser, default subparser and the subparsers
parser = argparse.ArgumentParser(
    description='Warden to iocage wrapper',
    usage=warden_usage()
)
subparsers = parser.add_subparsers()

auto_parser = subparsers.add_parser('auto')
auto_parser.add_argument('jail', action='store')
auto_parser.set_defaults(func=boot_jail_prop)

chroot_parser = subparsers.add_parser('chroot')
chroot_parser.add_argument('jail', action='store')
chroot_parser.set_defaults(func=chroot_jail)

create_parser = subparsers.add_parser('create')
create_parser.add_argument('tag', action='store')
create_parser.add_argument('--ipv4', action='store', dest='ip4')
create_parser.add_argument('--startauto', action='store_true', dest='boot')
create_parser.add_argument('--version', action='store', dest='release', default='10.2-RELEASE')
create_parser.add_argument('--vanilla', action='store_true')
create_parser.add_argument('--syslog', action='store_true')
create_parser.add_argument('--template', action='store', nargs=argparse.REMAINDER)
create_parser.add_argument('--logfile', action='store', dest=None)
create_parser.set_defaults(func=create_jail)

delete_parser = subparsers.add_parser('delete')
delete_parser.add_argument('jail', action='store')
delete_parser.add_argument('--confirm', action='store_true')
delete_parser.set_defaults(func=delete_jail)

list_parser = subparsers.add_parser('list')
list_parser.add_argument('-v', help='Wraps "iocage list --warden"',
                         action='store_true', dest='_long_list')
list_parser.set_defaults(func=list_jails)

set_parser = subparsers.add_parser('set')
set_parser.add_argument('set', action='store')
set_parser.add_argument('jail', action='store')
set_parser.set_defaults(func=set_jail_prop)

start_parser = subparsers.add_parser('start')
start_parser.add_argument('jail', action='store')
start_parser.set_defaults(func=start_jail)

stop_parser = subparsers.add_parser('stop')
stop_parser.add_argument('jail', action='store')
stop_parser.set_defaults(func=stop_jail)

template_parser = subparsers.add_parser('template')
template_parser.add_argument('list', action='store', nargs=argparse.REMAINDER)
template_parser.add_argument('create', action='store', nargs=argparse.REMAINDER)
template_parser.set_defaults(func=template_handling)
