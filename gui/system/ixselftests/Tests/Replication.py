#!/usr/local/bin/python
# Copyright (c) 2011, 2015-2017 iXsystems, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

import logging
import os
import re
import subprocess
import sys


def List():
    return ["replication"]

debug = False

tpath = None
if not ("/usr/local/www/freenasUI" in sys.path):
    tpath = list(sys.path)
    sys.path.extend([
        '/usr/local/www',
        '/usr/local/www/freenasUI',
    ])
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

import django
django.setup()

from freenasUI.freeadmin.apppool import appPool
from freenasUI.storage.models import Replication, REPL_RESULTFILE
from freenasUI.common.timesubr import isTimeBetween
from freenasUI.common.pipesubr import pipeopen
from freenasUI.common.locks import mntlock
from freenasUI.common.system import send_mail, get_sw_name

from system.ixselftests import TestObject


class replication(TestObject):
    def __init__(self, handler):
        super(self.__class__, self).__init__(handler)
        self._replications = Replication.objects.all()
        if tpath:
            sys.path = tpath

    def Enabled(self):
        # For now
        return len(self._replications) > 0

    def Test(self):
        status = True
        all_passed = True
        for replication in self._replications:
            remote = replication.repl_remote.ssh_remote_hostname.__str__()
            remote_port = replication.repl_remote.ssh_remote_port
            dedicateduser = replication.repl_remote.ssh_remote_dedicateduser
            cipher = replication.repl_remote.ssh_cipher
            remotefs = replication.repl_zfs.__str__()
            localfs = replication.repl_filesystem.__str__()
            last_snapshot = replication.repl_lastsnapshot.__str__()
            compression = replication.repl_compression.__str__()
            followdelete = not not replication.repl_followdelete
            recursive = not not replication.repl_userepl

            if not replication.repl_enabled:
                continue

            if cipher == 'fast':
                sshcmd = (
                    '/usr/bin/ssh -c arcfour256,arcfour128,blowfish-cbc,'
                    'aes128-ctr,aes192-ctr,aes256-ctr -i /data/ssh/replication'
                    ' -o BatchMode=yes -o StrictHostKeyChecking=yes'
                    # There's nothing magical about ConnectTimeout, it's an average
                    # of wiliam and josh's thoughts on a Wednesday morning.
                    # It will prevent hunging in the status of "Sending".
                    ' -o ConnectTimeout=7'
                )
            elif cipher == 'disabled':
                sshcmd = ('/usr/bin/ssh -ononeenabled=yes -ononeswitch=yes -i /data/ssh/replication -o BatchMode=yes'
                          ' -o StrictHostKeyChecking=yes'
                          ' -o ConnectTimeout=7')
            else:
                sshcmd = ('/usr/bin/ssh -i /data/ssh/replication -o BatchMode=yes'
                          ' -o StrictHostKeyChecking=yes'
                          ' -o ConnectTimeout=7')

            if dedicateduser:
                sshcmd = "%s -l %s" % (sshcmd, dedicateduser.encode('utf-8'))

            sshcmd = '%s -p %d %s' % (sshcmd, remote_port, remote)

            # Now we do a simple, stupid test for ssh
            rproc = pipeopen("%s /usr/bin/true" % sshcmd)
            output, error = rproc.communicate()
            error = error.strip('\n').strip('\r').replace('WARNING: enabled NONE cipher', '')
            if rproc.returncode:
                status = self._handler.Fail("replication remote access",
                                            "Could not log into remote host %s: %s" % (
                                                remote,
                                                error))
                continue
            self._handler.Pass("replication remote access", remote)

            remotefs_final = "%s%s%s" % (remotefs, localfs.partition('/')[1], localfs.partition('/')[2])

            if recursive:
                zfsproc = pipeopen('/sbin/zfs list -H -t snapshot -p -o name,creation -r "%s"' % (localfs), debug)
            else:
                zfsproc = pipeopen('/sbin/zfs list -H -t snapshot -p -o name,creation -r -d 1 "%s"' % (localfs), debug)

            output, error = zfsproc.communicate()
            if zfsproc.returncode:
                self._handler.Fail("replication",
                                   "Could not determine last available snapshot for dataset %s: %s" %(
                                       localfs,
                                       error))
                status = False
                continue
            self._handler.Pass("replication snapshot check", localfs)

            # Bi-directional replication: the remote side indicates that they are
            # willing to receive snapshots by setting readonly to 'on', which prevents
            # local writes.
            #
            # We expect to see "on" in the output, or cannot open '%s': dataset does not exist
            # in the error.  To be safe, also check for children's readonly state.
            may_proceed = False
            rzfscmd = '"zfs list -H -o readonly -t filesystem,volume -r %s"' % (remotefs_final)
            sshproc = pipeopen('%s %s' % (sshcmd, rzfscmd))
            output, error = sshproc.communicate()
            error = error.strip('\n').strip('\r').replace('WARNING: enabled NONE cipher', '')
            error_msg = None
            if sshproc.returncode:
                # Be conservative: only consider it's Okay when we see the expected result.
                if error == '' or output.split('\n')[0] == ("cannot open '%s': dataset does not exist" % (remotefs_final)):
                    pass
                else:
                    error_msg = error + ": " + output
            else:
                if output == '' or output.find('off') == -1:
                    pass
                else:
                    if output.find("off") != -1:
                        error_msg = "Remote dataset is not read-only"
                    else:
                        error_msg = output

            if error_msg:
                # This isn't a fatal issue for the test, so just mark it as a failure
                self._handler.Fail("replication read-only check", error_msg)
                all_passed = False
            else:
                self._handler.Pass("replicaiton read-only check", remotefs_final)

        if status:
            return self._handler.Pass(
                "replication", "%s tests passed" % ("all" if all_passed else "some")
            )
        else:
            return False
