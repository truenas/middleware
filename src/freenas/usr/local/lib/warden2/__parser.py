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
from __boot_set import __boot_jail_prop
from __chroot import __chroot_jail
from __create import __create_jail
from __delete import __delete_jail
from __list import __list_jails
from __set import __set_jail_prop
from __start import __start_jail
from __stop import __stop_jail
from __template import __template_handling
from __warden import __warden_usage


# Set up the parser, default subparser and the subparsers
parser = argparse.ArgumentParser(
    description='Warden to iocage wrapper',
    usage=__warden_usage()
)
subparsers = parser.add_subparsers()

_auto_parser = subparsers.add_parser('auto')
_auto_parser.add_argument('jail', action='store')
_auto_parser.set_defaults(func=__boot_jail_prop)

_chroot_parser = subparsers.add_parser('chroot')
_chroot_parser.add_argument('jail', action='store')
_chroot_parser.set_defaults(func=__chroot_jail)

_create_parser = subparsers.add_parser('create')
_create_parser.add_argument('tag', action='store')
_create_parser.add_argument('--ipv4', action='store', dest='ip4')
_create_parser.add_argument('--startauto', action='store_true', dest='boot')
_create_parser.add_argument('--version', action='store', dest='release', default='10.2-RELEASE')
_create_parser.add_argument('--vanilla', action='store_true')
_create_parser.add_argument('--syslog', action='store_true')
_create_parser.add_argument('--template', action='store', nargs=argparse.REMAINDER)
_create_parser.add_argument('--logfile', action='store', dest=None)
_create_parser.set_defaults(func=__create_jail)

_delete_parser = subparsers.add_parser('delete')
_delete_parser.add_argument('jail', action='store')
_delete_parser.add_argument('--confirm', action='store_true')
_delete_parser.set_defaults(func=__delete_jail)

_list_parser = subparsers.add_parser('list')
_list_parser.add_argument('-v', help='Wraps "iocage list --warden"',
                          action='store_true', dest='_long_list')
_list_parser.set_defaults(func=__list_jails)

_set_parser = subparsers.add_parser('set')
_set_parser.add_argument('set', action='store')
_set_parser.add_argument('jail', action='store')
_set_parser.set_defaults(func=__set_jail_prop)

_start_parser = subparsers.add_parser('start')
_start_parser.add_argument('jail', action='store')
_start_parser.set_defaults(func=__start_jail)

_stop_parser = subparsers.add_parser('stop')
_stop_parser.add_argument('jail', action='store')
_stop_parser.set_defaults(func=__stop_jail)

_template_parser = subparsers.add_parser('template')
_template_parser.add_argument('list', action='store', nargs=argparse.REMAINDER)
_template_parser.add_argument('create', action='store', nargs=argparse.REMAINDER)
_template_parser.set_defaults(func=__template_handling)
