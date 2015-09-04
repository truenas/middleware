#!/usr/bin/env python2.7
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
from __pipeopen import __pipeopen
from sys import stderr


def __set_jail_prop(args):
    """
    Take 2 arguments and supplies that to `iocage set` for the jail
    """
    if args.set in 'vnet-enable':
        args.set = 'vnet=on'
        _ip4 = __pipeopen(
            ['/usr/local/sbin/iocage',
             'get',
             'ip4_addr',
             '{0}'.format(args.jail)])
        if _ip4[0] != 0:
            print '  An error has occured'
        _ip4 = _ip4[1].rstrip().replace('DEFAULT|', '')
        __pipeopen(
            ['/usr/local/sbin/iocage',
             'set',
             'ip4_addr={0}'.format(_ip4),
             '{0}'.format(args.jail)])
    if args.set in ('nat-disable', 'nat-enable'):
        exit(0)
    (retcode, results_stdout, results_stderr) = __pipeopen(
        ['/usr/local/sbin/iocage',
         'set',
         '{0}'.format(args.set),
         '{0}'.format(args.jail)])
    if retcode == 0:
        print '  Property {0} set on {1}'.format(args.set, args.jail)
    else:
        print results_stdout
        stderr.write(results_stderr)
