#!/usr/local/bin/python2
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
import ctypes
import logging
import logging.config
import os
import pwd
import subprocess
import sys

from setproctitle import setproctitle
import daemon

HERE = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(HERE, '..'))
sys.path.append(os.path.join(HERE, '../..'))
sys.path.append('/usr/local/www')
sys.path.append('/usr/local/www/freenasUI')
sys.path.append('/usr/local/lib')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.settings import LOGGING

log = logging.getLogger('tools.runnow')
logging.config.dictConfig(LOGGING)

from freenasUI.common.log import log_traceback
from freenasUI.tasks.models import CronJob, Rsync


def main(args):

    setproctitle('runnow')

    if args.type == 'cronjob':
        model = CronJob
        attr = 'cron_user'
    else:
        model = Rsync
        attr = 'rsync_user'

    obj = model.objects.get(id=args.id)
    user = getattr(obj, attr).encode('utf8')

    libc = ctypes.cdll.LoadLibrary("libc.so.7")
    libutil = ctypes.cdll.LoadLibrary("libutil.so.9")
    libc.getpwnam.restype = ctypes.POINTER(ctypes.c_void_p)
    pwnam = libc.getpwnam(user)
    passwd = pwd.getpwnam(user)

    libutil.login_getpwclass.restype = ctypes.POINTER(
        ctypes.c_void_p
    )
    lc = libutil.login_getpwclass(pwnam)
    if lc and lc[0]:
        libutil.setusercontext(
            lc, pwnam, passwd.pw_uid, ctypes.c_uint(0x07ff)
        )

    os.setgid(passwd.pw_gid)
    libc.setlogin(user)
    libc.initgroups(user, passwd.pw_gid)
    os.setuid(passwd.pw_uid)

    if lc and lc[0]:
        libutil.login_close(lc)

    try:
        os.chdir(passwd.pw_dir)
    except:
        os.chdir('/')
    proc = subprocess.Popen(
        '%s | logger -t %s' % (obj.commandline(), args.type),
        shell=True,
        env={
            'PATH': (
                '/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:'
                '/usr/local/sbin:/root/bin'
            ),
        },
    )
    proc.communicate()


if __name__ == '__main__':

    context = daemon.DaemonContext(
        working_directory='/root',
        umask=0o002,
        stdout=sys.stdout,
        stdin=sys.stdin,
        stderr=sys.stderr,
        detach_process=True,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--type', help='Job type')
    parser.add_argument('-i', '--id', help='ID of the job')
    args = parser.parse_args()

    with context:
        log.debug("Entered in daemon context")
        try:
            main(args)
        except Exception, e:
            log.debug('Exception on run now')
            log_traceback(log=log)

    log.debug("Exiting runnow process")
    sys.exit(0)
