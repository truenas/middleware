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
import syslog
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
syslog.openlog("autorepl", syslog.LOG_CONS | syslog.LOG_PID)

sshcmd = '/usr/bin/ssh -i /data/ssh/replication -o BatchMode=yes -o StrictHostKeyChecking=yes -q'

mypid = os.getpid()
inprogress_tag = 'INPROGRESS-%d' % (mypid)
templog = '/tmp/repl-%d' % (mypid)

syslog.syslog(syslog.LOG_DEBUG, "Autosnap replication started (our tag: %s)" % (inprogress_tag))
syslog.syslog(syslog.LOG_DEBUG, "temp log file: %s" % (templog))

# Detect if another instance is running
def ExitIfRunning(theirpid):
    syslog.syslog(syslog.LOG_DEBUG, "Checking if process %d is still alive" % (theirpid))
    from os import kill
    try:
        os.kill(theirpid, 0)
        # If we reached here, there is another process in progress
        syslog.syslog(syslog.LOG_DEBUG, "Process %d still working, quitting" % (theirpid))
        exit(0)
    except OSError:
        pass
    syslog.syslog(syslog.LOG_NOTICE, "Process %d gone, will cleanup its work" % (theirpid))

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
    known_latest_snapshot = ''
    expected_local_snapshot = ''

    # Test if there is work to do, if so, own them
    MNTLOCK.lock()
    syslog.syslog(syslog.LOG_DEBUG, "Checking dataset %s" % (localfs))
    zfsproc = pipeopen('/sbin/zfs list -Ht snapshot -o name,freenas:state -r -S creation -d 1 %s' % (localfs))
    zfsproc.wait()
    output = zfsproc.communicate()[0]
    if output != '':
        snapshots_list = output.split('\n')
        found_latest = False
        for snapshot_item in snapshots_list:
            if snapshot_item != '':
                snapshot, state = snapshot_item.split('\t')
                if not found_latest:
                    syslog.syslog(syslog.LOG_DEBUG, "Snapshot: %s State: %s" % (snapshot, state))
                    if state == 'LATEST':
                        found_latest = True
                        known_latest_snapshot = snapshot
                        syslog.syslog(syslog.LOG_DEBUG, "Snapshot %s is the recorded latest snapshot" % (snapshot))
                        continue
                    elif state == 'NEW':
                        wanted_list.insert(0, snapshot)
                        syslog.syslog(syslog.LOG_DEBUG, "Snapshot %s added to wanted list" % (snapshot))
                    elif state[:11] == 'INPROGRESS-':
                        # Rob ownership for orphan snapshot, but quit if
                        # there is already inprogres transfer.
                        ExitIfRunning(int(state[11:]))
                        wanted_list.insert(0, snapshot)
                        syslog.syslog(syslog.LOG_DEBUG, "Snapshot %s added to wanted list (continuing failed backup)" % (snapshot))
                    elif state == '-':
                        # The snapshot is already replicated, or is not
                        # an automated snapshot.
                        syslog.syslog(syslog.LOG_DEBUG, "Snapshot %s unwanted" % (snapshot))
                        continue
                    else:
                        # This should be exception but skip for now.
                        continue
                    # NEW or INPROGRESS (stale), change the state to reflect that
                    # we own the snapshot by using INPROGRESS-{pid}.
                    system('/sbin/zfs set freenas:state=%s %s' % (inprogress_tag, snapshot))
                else:
                    # assert (known_latest_snapshot != '') because found_latest
                    if state != '-':
                        system('/sbin/zfs set freenas:state=%s %s' % (inprogress_tag, known_latest_snapshot))
                        system('/sbin/zfs set freenas:state=LATEST %s' % (snapshot))
                        wanted_list.insert(0, known_latest_snapshot)
                        syslog.syslog(syslog.LOG_DEBUG, "Snapshot %s added to wanted list (was LATEST)" % (snapshot))
                        known_latest_snapshot = snapshot
                        syslog.syslog(syslog.LOG_ALERT, "Snapshot %s became latest snapshot" % (snapshot))
    MNTLOCK.unlock()

    # If there is nothing to do, go through next replication entry
    if len(wanted_list) == 0:
        continue

    if known_latest_snapshot != '':
        # Check if it matches remote snapshot
        rzfscmd = '"zfs list -Hr -o name -S creation -t snapshot -d 2 %s | head -n 1 | cut -d@ -f2"' % (remotefs)
        sshproc = pipeopen('%s %s %s' % (sshcmd, remote, rzfscmd))
        output = sshproc.communicate()[0]
        if output != '':
            expected_local_snapshot = '%s@%s' % (localfs, output.split('\n')[0])
            if expected_local_snapshot == last_snapshot:
                # Accept: remote and local snapshots matches
                syslog.syslog(syslog.LOG_DEBUG, "Found matching latest snapshot %s remotely" % (last_snapshot))
                pass
            elif expected_local_snapshot == known_latest_snapshot:
                # Accept
                syslog.syslog(syslog.LOG_DEBUG, "Found matching latest snapshot %s remotely (but not the recorded one)" % (known_latest_snapshot))
                last_snapshot = known_latest_snapshot
            else:
                # Do we have it locally? if yes then mark it immediately
                syslog.syslog(syslog.LOG_INFO, "Can not locate expected snapshot %s, looking more carefully" % (expected_local_snapshot))
                MNTLOCK.lock()
                zfsproc = pipeopen('/sbin/zfs list -Ht snapshot -o name,freenas:state %s' % (expected_local_snapshot))
                output = zfsproc.communicate()[0]
                if output != '':
                    last_snapshot, state = output.split('\n')[0].split('\t')
                    syslog.syslog(syslog.LOG_INFO, "Marking %s as latest snapshot" % (last_snapshot))
                    if state == '-':
                        system('/sbin/zfs inherit freenas:state %s' % (known_latest_snapshot))
                        system('/sbin/zfs set freenas:state=LATEST %s' % (last_snapshot))
                        known_latest_snapshot = last_snapshot
                else:
                    syslog.syslog(syslog.LOG_ALERT, "Can not locate a proper local snapshot for %s" % (localfs))
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
            syslog.syslog(syslog.LOG_NOTICE, "Can not locate %s on remote system, starting from there" % (known_latest_snapshot))
            # Reset the "latest" snapshot to a new one.
            system('/sbin/zfs set freenas:state=%s %s' % (inprogress_tag, known_latest_snapshot))
            wanted_list.insert(0, known_latest_snapshot)
            last_snapshot = ''
            known_latest_snapshot = ''
    if known_latest_snapshot == '':
         # Create remote filesystem
         syslog.syslog(syslog.LOG_NOTICE, "Creating %s on remote system" % (remotefs))
         replcmd = '%s %s /sbin/zfs create -p %s' % (sshcmd, remote, remotefs)
         system(replcmd)
         last_snapshot = ''
    else:
         last_snapshot = known_latest_snapshot

    for snapname in wanted_list:
        #if replication.repl_limit != 0:
        #    limit = ' | /usr/local/bin/throttle -K %d' % replication.repl_limit
        #else:
        #    limit = ''
        limit = ''
        if last_snapshot == '':
            replcmd = '(/sbin/zfs send %s%s%s | %s %s "/sbin/zfs receive -F -d %s && echo Succeeded.") > %s 2>&1' % (Rflag, snapname, limit, sshcmd, remote, remotefs, templog)
        else:
            replcmd = '(/sbin/zfs send %s-I %s %s%s | %s %s "/sbin/zfs receive -F -d %s && echo Succeeded.") > %s 2>&1' % (Rflag, last_snapshot, snapname, limit, sshcmd, remote, remotefs, templog)
        system(replcmd)
        f = open(templog)
        msg = f.read()
        f.close()
        os.remove(templog)
        syslog.syslog(syslog.LOG_DEBUG, "Replication result: %s" % (msg))
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
            else:
                syslog.syslog(syslog.LOG_ALERT, "Remote and local mismatch after replication: %s vs %s" % (expected_local_snapshot, snapname))
                localfs, snaptime = snapname.split('@')
                dataset = localfs.split('/')[-1]
                rzfscmd = '"zfs list -Ho name -t snapshot %s/%s@%s | head -n 1 | cut -d@ -f2"' % (remotefs, dataset, snaptime)
                sshproc = pipeopen('%s %s %s' % (sshcmd, remote, rzfscmd))
                output = sshproc.communicate()[0]
                if output != '':
                    expected_local_snapshot = '%s@%s' % (localfs, output.split('\n')[0])
                    if expected_local_snapshot == snapname:
                        syslog.syslog(syslog.LOG_ALERT, "Snapshot %s already exist on remote, marking as such" % (snapname))
                        system('%s %s "/sbin/zfs inherit -r freenas:state %s"' % (sshcmd, remote, remotefs))
                        # Replication was successful, mark as such
                        MNTLOCK.lock()
                        system('/sbin/zfs inherit freenas:state %s' % (snapname))
                        MNTLOCK.unlock()
                        continue

        # Something wrong, report.
        syslog.syslog(syslog.LOG_ALERT, "Replication of %s failed with %s" % (snapname, msg))
        error, errmsg = send_mail(subject="Replication failed!", text=\
            """
Hello,
    The system was unable to replicate snapshot %s to %s
======================
%s
            """ % (localfs, remote, msg), interval = timedelta(hours = 2), channel = 'autorepl')
        break

syslog.syslog(syslog.LOG_DEBUG, "Autosnap replication finished (our tag: %s)" % (inprogress_tag))
