#+
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


import os
import sys
import launchd
import subprocess
from utils import fail


PLIST = {
    'Label': 'org.freenas.test.mach.ipc-server',
    'RunAtLoad': True,
    'StandardOutPath': os.path.join(os.getenv('LOGPATH'), 'echoserver.log'),
    'StandardErrorPath': os.path.join(os.getenv('LOGPATH'), 'echoserver.log'),
    'ProgramArguments': [
        sys.executable,
        os.path.join(os.getcwd(), 'echoserver.py')
    ],
    'MachServices': [
        'org.freenas.test.mach.ipc-server'
    ]
}


def main():
    # Start service
    try:
        l = launchd.Launchd()
        l.load(PLIST)
    except OSError, e:
        fail('Cannot load launchd job: {0}', e)

    # Ensure service is running
    job = l.jobs['org.freenas.test.mach.ipc-server']
    if 'PID' not in job:
        l.unload('org.freenas.test.mach.ipc-server')
        fail('Service died')

    # Start client
    if subprocess.call([sys.executable, os.path.join(os.getcwd(), 'echoclient.py')]) != 0:
        l.unload('org.freenas.test.mach.ipc-server')
        fail('Client failed')

    # Stop service
    l.unload('org.freenas.test.mach.ipc-server')


if __name__ == '__main__':
    main()