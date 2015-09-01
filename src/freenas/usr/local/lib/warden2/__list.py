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


def __list_jails(args):
    """
    Wraps `warden list` and `warden list -v` to `iocage list`
    and `iocage list --warden` respectively.
    """
    if args._long_list:
        id_num = 1
        (retcode, results_stdout, results_stderr) = __pipeopen(
            ['/usr/local/sbin/iocage',
             'list',
             '--warden'])
        while 'id: -' in results_stdout:
            results_stdout = results_stdout.replace('id: -', 'id: {0}'.format(id_num), 1)
            id_num += 1
        results_stdout = results_stdout.replace(': off', ': Disabled')
        results_stdout = results_stdout.replace(': on', ': Enabled')
        results_stdout = results_stdout.replace(': down', ': Stopped')
        results_stdout = results_stdout.replace(': up', ': Running')
        results_stdout = results_stdout.replace(': None', ': ')
        results_stdout = results_stdout.replace(': none', ': ')
        results_stdout = results_stdout.replace('type: jail', 'type: standard')
        results_stdout = results_stdout.replace('type: jail', 'type: pluginjail')
        print results_stdout
    else:
        (retcode, results_stdout, results_stderr) = __pipeopen(
            ['/usr/local/sbin/iocage', 'list'], do_print=True)
