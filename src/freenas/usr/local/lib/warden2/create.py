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
import platform
from sys import stderr
from fetch import fetch_jails
import pipeopen
from rel import rel_list


def create_jail(args):
    """
    This wraps `warden create` and translates the syntax to `iocage create`.
    """
    # iocage looks for 'MAJOR.MINOR-RELEASE' without the patch level, this strips the patch level
    host_release = '-'.join(platform.release().split('-')[:2])
    if args.boot:
        args.boot = 'on'
    else:
        args.boot = 'off'

    # Check if the user supplied a RELEASE, otherwise assume hosts RELEASE
    if not args.release:
        args.release = host_release

    # If iocage doesn't have the RELEASE already fetched, do so now
    if rel_list(args) is False:
        print '  Fetching:', args.release
        fetch_jails(args)

    print '  Creating jail, please wait...'
    (retcode, results_stdout, results_stderr) = pipeopen(
        ['/usr/local/sbin/iocage',
         'create',
         'tag={0}'.format(args.tag),
         'vnet=off',
         'ip4_addr=DEFAULT|{0}'.format(args.ip4),
         'boot={0}'.format(args.boot),
         'release={0}'.format(args.release)])
    if retcode == 0:
        print '  Jail created!'
    else:
        print results_stdout
        stderr.write(results_stderr)
