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
import time
import datetime
import subprocess
import signal
from dsl import load_file


def interrupt(signal, frame):
    error('Build interrupted by SIGINT')


def sh(*args, **kwargs):
    logfile = kwargs.pop('log', None)
    cmd = os.path.expandvars(' '.join(args))
    if logfile:
        mkdirp(os.path.dirname(logfile))
        f = open(logfile, 'w')

    return subprocess.call(cmd, stdout=f if logfile else None, stderr=subprocess.STDOUT, shell=True)


def sh_str(*args, **kwargs):
    logfile = kwargs.pop('log', None)
    cmd = os.path.expandvars(' '.join(args))
    if logfile:
        f = open(logfile, 'w')

    try:
        return subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError:
        return None


def setup_env():
    signal.signal(signal.SIGINT, interrupt)
    dsl = load_file('${BUILD_CONFIG}/env.pyd', os.environ)
    for k, v in dsl.items():
        if k.isupper():
            os.environ[k] = v


def mkdirp(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def env(name, default=None):
    return os.getenv(name, default)


def e(s):
    return os.path.expandvars(s)


def objdir(path):
    return os.path.join(env('MAKEOBJDIRPREFIX'), path)


def elapsed():
    timestamp = env('BUILD_STARTED', str(int(time.time())))
    td = int(timestamp)
    return str(datetime.timedelta(seconds=time.time() - td))


def info(fmt, *args):
    print '[{0}] ==> '.format(elapsed()) + e(fmt.format(*args))


def debug(fmt, *args):
    if env('BUILD_LOGLEVEL') == 'DEBUG':
        print '[{0}] ==> '.format(elapsed()) + e(fmt.format(*args))


def error(fmt, *args):
    print '[{0}] ==> ERROR: '.format(elapsed()) + e(fmt.format(*args))
    sys.exit(1)