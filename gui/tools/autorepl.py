#!/usr/bin/env python
#-
# Copyright (c) 2011 iXsystems, Inc.
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

import sys
sys.path.append('/usr/local/www')
sys.path.append('/usr/local/www/freenasUI')

from freenasUI import settings

from django.core.management import setup_environ
setup_environ(settings)

import os
import re
from datetime import timedelta
from time import sleep
from freenasUI.storage.models import Task, Replication
from freenasUI.common.pipesubr import setname, pipeopen, system
from freenasUI.common.locks import mntlock
from freenasUI.common.system import send_mail

# DESIGN NOTES
#
# A snapshot transists its state in its lifetime this way:
#   NEW:                        A newly created snapshot by autosnap
#   INPROGRESS-123:             A snapshot being replicated by process 123
#   LATEST:                     A snapshot marked to be the latest one
#   -:                          The replication system no longer cares this.
#

MNTLOCK=mntlock()
setname('autorepl')

sshcmd = '/usr/bin/ssh -i /data/ssh/replication -o BatchMode=yes -o StrictHostKeyChecking=yes -q'

mypid = os.getpid()
inprogress_tag = 'INPROGRESS-%d' % (mypid)
templog = '/tmp/repl-%d' % (mypid)

# Detect if another instance is running
def ExitIfRunning(theirpid):
    from os import kill
    try:
        os.kill(theirpid, 0)
        # If we reached here, there is another process in progress
        exit(0)
    except:
        pass

# TODO: use a better way to synchornize with snapshotter
sleep(2)

# Traverse all replication tasks
replication_tasks = Replication.objects.all()
for replication in replication_tasks:
    remote = replication.repl_remote.ssh_remote_hostname.__str__()
    remotefs = replication.repl_zfs.__str__()
    localfs = replication.repl_mountpoint.mp_path[5:].__str__()
    last_snapshot = replication.repl_lastsnapshot.__str__()

    if replication.repl_userepl:
        Rflag = '-R '
    else:
        Rflag = ''

    wanted_list = []
    release_list = []
    expected_local_snapshot = ''

    # Test if there is work to do, if so, own them
    MNTLOCK.lock()
    zfsproc = pipeopen('/sbin/zfs list -Ht snapshot -o name,freenas:state -r -s creation -d 1 %s' % (localfs))
    zfsproc.wait()
    output = zfsproc.communicate()[0]
    if output != '':
        snapshots_list = output.split('\n')
        for snapshot_item in snapshots_list:
             if snapshot_item != '':
                  snapshot, state = snapshot_item.split('\t')
                  if state == 'LATEST':
                       release_list.append(snapshot)
                       MNTLOCK.unlock()
                       continue
                  elif state == 'NEW':
                       wanted_list.append(snapshot)
                  elif state[:11] == 'INPROGRESS-':
                       # Rob ownership for orphan snapshot, but quit if
                       # there is already inprogres transfer.
                       ExitIfRunning(int(state[11:]))
                       wanted_list.append(snapshot)
                  elif state == '-':
                       # The snapshot is already replicated, or is not
                       # an automated snapshot.
                       MNTLOCK.unlock()
                       continue
                  else:
                       # This should be exception but skip for now.
                       MNTLOCK.unlock()
                       continue
                  # NEW or INPROGRESS (stale), change the state to reflect that
                  # we own the snapshot by using INPROGRESS-{pid}.
                  system('/sbin/zfs set freenas:state=%s %s' % (inprogress_tag, snapshot))
    MNTLOCK.unlock()

    # If there is nothing to do, go through next replication entry
    if len(wanted_list) == 0:
        continue

    if len(release_list) > 1:
        # This should never happen, report this situation.
        error, errmsg = send_mail(subject="Replication failed!", text=\
            """
Hello,
    The replication failed for the local ZFS %s because the local state is mangled.
    This should never happen and manual intervention is required.
                    """ % (localfs), interval = timedelta(hours = 2), channel = 'autorepl')
         # The user have to 'zfs inherit -r freenas:state fs' then reconfigure replicator
        continue
    elif len(release_list) == 1:
        # Check if it matches remote snapshot
        rzfscmd = '"zfs list -Hr -o name -S creation -t snapshot -d 2 %s | head -n 1 | cut -d@ -f2"' % (remotefs)
        sshproc = pipeopen('%s %s %s' % (sshcmd, remote, rzfscmd))
        output = sshproc.communicate()[0]
        if output != '':
            expected_local_snapshot = '%s@%s' % (localfs, output.split('\n')[0])
            if expected_local_snapshot == last_snapshot:
                # Accept: remote and local snapshots matches
                pass
            elif expected_local_snapshot == release_list[0]:
                # Accept
                last_snapshot = release_list[0]
            else:
                # Do we have it locally? if yes then mark it immediately
                MNTLOCK.lock()
                zfsproc = pipeopen('/sbin/zfs list -Ht snapshot -o name,freenas:state %s' % (expected_local_snapshot))
                output = zfsproc.communicate()[0]
                if output != '':
                    last_snapshot, state = output.split('\n')[0].split('\t')
                    if state == '-':
                        system('/sbin/zfs inherit freenas:state %s' % (release_list[0]))
                        system('/sbin/zfs set freenas:state=LATEST %s' % (last_snapshot))
                        release_list = [last_snapshot]
                else:
                    # Can NOT proceed any further.  Report this situation.
                    error, errmsg = send_mail(subject="Replication failed!", text=\
                        """
Hello,
    The replication failed for the local ZFS %s because the remote system have
    have diveraged snapshot with us.
                        """ % (localfs), interval = timedelta(hours = 2), channel = 'autorepl')
                    MNTLOCK.unlock()
                    continue
                MNTLOCK.unlock()
        else:
            # Reset the "latest" snapshot to a new one.
            system('/sbin/zfs set freenas:state=NEW %s' % (release_list[0]))
            release_list = []
            last_snapshot = ''
    if len(release_list) == 0:
         # Create remote filesystem
         replcmd = '%s %s /sbin/zfs create -p %s' % (sshcmd, remote, remotefs)
         system(replcmd)
         last_snapshot = ''
    else:
         last_snapshot = release_list[0]

    for snapname in wanted_list:
        if replication.repl_limit != 0:
            limit = ' | /usr/local/bin/throttle -K %d' % replication.repl_limit
        else:
            limit = ''
        if last_snapshot == '':
            replcmd = '/sbin/zfs send %s%s%s | %s %s "/sbin/zfs receive -F -d %s && echo Succeeded." > %s 2>&1' % (Rflag, snapname, limit, sshcmd, remote, remotefs, templog)
        else:
            replcmd = '/sbin/zfs send %s-I %s %s%s | %s %s "/sbin/zfs receive -F -d %s && echo Succeeded." > %s 2>&1' % (Rflag, last_snapshot, snapname, limit, sshcmd, remote, remotefs, templog)
        system(replcmd)
        f = open(templog)
        msg = f.read()
        f.close()
        os.remove(templog)
        # Determine if the remote side have the snapshot we have now.
        rzfscmd = '"zfs list -Hr -o name -S creation -t snapshot -d 2 %s | head -n 1 | cut -d@ -f2"' % (remotefs)
        sshproc = pipeopen('%s %s %s' % (sshcmd, remote, rzfscmd))
        output = sshproc.communicate()[0]
        if output != '':
            expected_local_snapshot = '%s@%s' % (localfs, output.split('\n')[0])
            if expected_local_snapshot == snapname:
                system('%s %s "/sbin/zfs inherit -r freenas:state %s"' % (sshcmd, remote, remotefs))
                # Replication was successful, mark as such
                MNTLOCK.lock()
                if last_snapshot != '':
                    system('/sbin/zfs inherit freenas:state %s' % (last_snapshot))
                last_snapshot = snapname
                system('/sbin/zfs set freenas:state=LATEST %s' % (last_snapshot))
                MNTLOCK.unlock()
                replication.repl_lastsnapshot = last_snapshot
                replication.save()
                continue

        # Something wrong, report.
        error, errmsg = send_mail(subject="Replication failed!", text=\
            """
Hello,
    The system was unable to replicate snapshot %s to %s
======================
%s
            """ % (localfs, remote, msg), interval = timedelta(hours = 2), channel = 'autorepl')

