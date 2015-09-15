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
from subprocess import Popen, PIPE
from sys import stderr


def pipeopen(command_list, do_print=False, shell=False):
    """
    The magic sauce that runs the shell command specified by
    `command_list` and waits for it to finish and returns the returncode
    of the process, stdout and stderr in the following format:
    (retcode, stdout, stderr).
    If the (optional) do_print flag is set as true it will print
    the stdout and stderr streams appropriately.

    Example Usage:
    (myretcode, mystdout, mystderr) = pipeopen(['/bin/echo', 'hello'])
    """
    if shell:
            proc = Popen(command_list, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=False,
                         shell=True)
    else:
        proc = Popen(command_list, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=False)
    proc.wait()
    (results_stdout, results_stderr) = proc.communicate()
    retcode = proc.returncode
    if do_print:
        if retcode != 0:
            stderr.write(results_stderr)
        print results_stdout
    return (retcode, results_stdout, results_stderr)
