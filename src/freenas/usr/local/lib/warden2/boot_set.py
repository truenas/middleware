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
import pipeopen
from sys import stderr


def boot_jail_prop(args):
    """
    Take 1 argument and supplies that to `iocage set boot` for the jail
    """
    print '  Toggling jail property boot on {0}'.format(args.jail)
    (retcode, results_stdout, results_stderr) = pipeopen(
        ['/usr/local/sbin/iocage',
         'get',
         'boot',
         '{0}'.format(args.jail)])
    if 'off' in results_stdout:
        (retcode, results_stdout, results_stderr) = pipeopen(
            ['/usr/local/sbin/iocage',
             'set',
             'boot=on',
             '{0}'.format(args.jail)])
        if retcode == 0:
            print '  Property boot set on {0}'.format(args.jail)
        else:
            print results_stdout
            stderr.write(results_stderr)
    else:
        (retcode, results_stdout, results_stderr) = pipeopen(
            ['/usr/local/sbin/iocage',
             'set',
             'boot=off',
             '{0}'.format(args.jail)])
        if retcode == 0:
            print '  Property boot unset on {0}'.format(args.jail)
        else:
            print results_stdout
            stderr.write(results_stderr)
