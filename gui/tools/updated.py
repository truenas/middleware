#!/usr/local/bin/python2
#
# Copyright 2014 iXsystems, Inc.
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
import fcntl
import logging
import logging.config
import os
import sys

from setproctitle import setproctitle
import daemon

HERE = os.path.abspath(os.path.dirname(__file__))
sys.path.append(os.path.join(HERE, '..'))
sys.path.append(os.path.join(HERE, '../..'))
sys.path.append('/usr/local/www')
sys.path.append('/usr/local/www/freenasUI')
sys.path.append('/usr/local/lib')

os.environ['DJANGO_SETTINGS_MODULE'] = 'freenasUI.settings'

import django
django.setup()

from freenasUI.settings import LOGGING

log = logging.getLogger('tools.updated')
logging.config.dictConfig(LOGGING)

from freenasOS import Update, Manifest
from freenasOS.Exceptions import ManifestInvalidSignature
from freenasUI.common.log import log_traceback
from freenasUI.system.utils import UpdateHandler, create_update_alert


class PidFile(object):
    '''
    Context manager that locks a pid file.
    Implemented as class not generator because daemon.py is calling __exit__
    with no parameters instead of the None, None, None specified by PEP-343.

    Based on:
    http://code.activestate.com/recipes/
    577911-context-manager-for-a-daemon-pid-file/
    '''

    def __init__(self, path):
        self.path = path
        self.pidfile = None

    def __enter__(self):
        self.pidfile = open(self.path, 'a+')
        try:
            fcntl.flock(self.pidfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise SystemExit('Already running according to ' + self.path)
        self.pidfile.seek(0)
        self.pidfile.truncate()
        self.pidfile.write(str(os.getpid()))
        self.pidfile.flush()
        self.pidfile.seek(0)
        return self.pidfile

    def __exit__(self, *args, **kwargs):
        try:
            if os.path.exists(self.path):
                os.unlink(self.path)
            self.pidfile.close()
        except IOError:
            pass


def main(handler, args):

    setproctitle('updated')

    handler.pid = os.getpid()
    handler.dump()

    if args.download:
        log.debug('Starting DownloadUpdate')
        Update.DownloadUpdate(
            args.train,
            args.cache,
            check_handler=handler.get_handler,
            get_handler=handler.get_file_handler,
        )
        log.debug('DownloadUpdate finished')

    new_manifest = Manifest.Manifest(require_signature=True)
    try:
        new_manifest.LoadPath(args.cache + '/MANIFEST')
    except ManifestInvalidSignature as e:
        log.error("Cached manifest has invalid signature: %s" % str(e))
        raise
    update_version = new_manifest.Version()

    if args.apply:
        log.debug('Starting ApplyUpdate')
        handler.reboot = Update.ApplyUpdate(
            args.cache,
            install_handler=handler.install_handler,
        )
        log.debug('ApplyUpdate finished')
        if handler.reboot:
            # Create Alert that update is applied and system should now be rebooted
            create_update_alert(update_version)


if __name__ == '__main__':

    pidfile = PidFile('/var/run/updated.pid')

    context = daemon.DaemonContext(
        working_directory='/root',
        umask=0o002,
        pidfile=pidfile,
        stdout=sys.stdout,
        stdin=sys.stdin,
        stderr=sys.stderr,
        detach_process=True,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-a', '--apply', action='store_true',
        help='Apply updates'
    )
    parser.add_argument(
        '-d', '--download', action='store_true',
        help='Download updates'
    )
    parser.add_argument('-t', '--train', help='Train name')
    parser.add_argument('-c', '--cache', help='Path to the cache directory')
    args = parser.parse_args()

    handler = UpdateHandler(apply_=args.apply)
    handler.dump()
    print(handler.uuid)

    sys.stdout.flush()

    log.debug("Entering in daemon mode")

    with context:
        log.debug("Entered in daemon context")
        try:
            main(handler, args)
        except Exception as e:
            log.debug('Exception on update')
            log_traceback(log=log)
            handler.error = str(e)
        handler.finished = True
        handler.dump()

    log.debug("Exiting daemon process")

    sys.exit(0)
