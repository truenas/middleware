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

import cPickle
import datetime
import logging
import os
import subprocess
import sys

sys.path.extend([
    '/usr/local/www',
    '/usr/local/www/freenasUI',
])

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.freeadmin.apppool import appPool
from freenasUI.storage.models import Replication, REPL_RESULTFILE
from freenasUI.common.timesubr import isTimeBetween
from freenasUI.common.pipesubr import pipeopen, system
from freenasUI.common.locks import mntlock
from freenasUI.common.system import send_mail

# DESIGN NOTES
#
# A snapshot transists its state in its lifetime this way:
#   NEW:                        A newly created snapshot by autosnap
#   LATEST:                     A snapshot marked to be the latest one
#   -:                          The replication system no longer cares this.
#

log = logging.getLogger('tools.autorepl')

# Set to True if verbose log desired
debug = False

# Detect if another instance is running
def exit_if_running(pid):
    log.debug("Checking if process %d is still alive" % (pid, ))
    try:
        os.kill(pid, 0)
        # If we reached here, there is another process in progress
        log.debug("Process %d still working, quitting" % (pid, ))
        sys.exit(0)
    except OSError:
        log.debug("Process %d gone" % (pid, ))

appPool.hook_tool_run('autorepl')

MNTLOCK = mntlock()

mypid = os.getpid()
templog = '/tmp/repl-%d' % (mypid)

now = datetime.datetime.now().replace(microsecond=0)
if now.second < 30 or now.minute == 59:
    now = now.replace(second=0)
else:
    now = now.replace(minute=now.minute + 1, second=0)
now = datetime.time(now.hour, now.minute)

# (mis)use MNTLOCK as PIDFILE lock.
locked = True
try:
    MNTLOCK.lock_try()
except IOError:
    locked = False
if not locked:
    sys.exit(0)

AUTOREPL_PID = -1
try:
    with open('/var/run/autorepl.pid') as pidfile:
        AUTOREPL_PID = int(pidfile.read())
except:
    pass

if AUTOREPL_PID != -1:
    exit_if_running(AUTOREPL_PID)

with open('/var/run/autorepl.pid', 'w') as pidfile:
    pidfile.write('%d' % mypid)

MNTLOCK.unlock()

# At this point, we are sure that only one autorepl instance is running.

log.debug("Autosnap replication started")
log.debug("temp log file: %s" % (templog, ))

try:
    with open(REPL_RESULTFILE, 'rb') as f:
        data = f.read()
    results = cPickle.loads(data)
except:
    results = {}

# Traverse all replication tasks
replication_tasks = Replication.objects.all()
for replication in replication_tasks:
    if not isTimeBetween(now, replication.repl_begin, replication.repl_end):
        continue

    if not replication.repl_enabled:
        log.warn("%s replication not enabled" % replication)
        continue

    remote = replication.repl_remote.ssh_remote_hostname.__str__()
    remote_port = replication.repl_remote.ssh_remote_port
    dedicateduser = replication.repl_remote.ssh_remote_dedicateduser
    cipher = replication.repl_remote.ssh_cipher
    remotefs = replication.repl_zfs.__str__()
    localfs = replication.repl_filesystem.__str__()
    last_snapshot = replication.repl_lastsnapshot.__str__()
    resetonce = replication.repl_resetonce
    compression = replication.repl_compression.__str__()

    if cipher == 'fast':
        sshcmd = ('/usr/bin/ssh -c arcfour256,arcfour128,blowfish-cbc,'
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
        sshcmd = "%s -l %s" % (
            sshcmd,
            dedicateduser.encode('utf-8'),
            )

    if replication.repl_userepl:
        Rflag = '-R '
    else:
        Rflag = ''

    wanted_list = []
    known_latest_snapshot = ''
    expected_local_snapshot = ''

    localfs_split = localfs.split('/')

    if len(localfs_split) > 1:
        remotefs_final = "%s/%s" % (remotefs, "/".join(localfs_split[1:]))
        if len(localfs_split) > 2:
            remotefs_parent = "%s/%s" % (remotefs, "/".join(localfs_split[1:-1]))
        else:
            remotefs_parent = "%s/%s" % (remotefs, localfs_split[1])
    else:
        remotefs_final = remotefs
        remotefs_parent = remotefs

    # Test if there is work to do, if so, own them
    MNTLOCK.lock()
    log.debug("Checking dataset %s" % (localfs))
    zfsproc = pipeopen('/sbin/zfs list -Ht snapshot -o name,freenas:state -r -d 1 %s' % (localfs), debug)
    output, error = zfsproc.communicate()
    if zfsproc.returncode:
        log.warn('Could not determine last available snapshot for dataset %s: %s' % (
            localfs,
            error,
            ))
        MNTLOCK.unlock()
        continue
    if output != '':
        snapshots_list = output.split('\n')
        snapshots_list.reverse()
        found_latest = False
        for snapshot_item in snapshots_list:
            if snapshot_item != '':
                snapshot, state = snapshot_item.split('\t')
                if found_latest:
                    # assert (known_latest_snapshot != '') because found_latest
                    if state != '-':
                        system('/sbin/zfs set freenas:state=NEW %s' % (known_latest_snapshot))
                        system('/sbin/zfs set freenas:state=LATEST %s' % (snapshot))
                        system('/sbin/zfs hold -r freenas:repl %s' % (known_latest_snapshot))
                        system('/sbin/zfs hold -r freenas:repl %s' % (snapshot))
                        wanted_list.insert(0, known_latest_snapshot)
                        log.debug("Snapshot %s added to wanted list (was LATEST)" % (snapshot))
                        known_latest_snapshot = snapshot
                        log.warn("Snapshot %s became latest snapshot" % (snapshot))
                else:
                    log.debug("Snapshot: %s State: %s" % (snapshot, state))
                    if state == 'LATEST' and not resetonce:
                        found_latest = True
                        known_latest_snapshot = snapshot
                        log.debug("Snapshot %s is the recorded latest snapshot" % (snapshot))
                    elif state == 'NEW' or resetonce:
                        wanted_list.insert(0, snapshot)
                        log.debug("Snapshot %s added to wanted list" % (snapshot))
                    elif state.startswith('INPROGRESS'):
                        # For compatibility with older versions
                        wanted_list.insert(0, snapshot)
                        system('/sbin/zfs set freenas:state=NEW %s' % (snapshot))
                        system('/sbin/zfs hold -r freenas:repl %s' % (snapshot))
                        log.debug("Snapshot %s added to wanted list (stale)" % (snapshot))
                    elif state == '-':
                        # The snapshot is already replicated, or is not
                        # an automated snapshot.
                        log.debug("Snapshot %s unwanted" % (snapshot))
                    else:
                        # This should be exception but skip for now.
                        MNTLOCK.unlock()
                        continue
    MNTLOCK.unlock()

    # If there is nothing to do, go through next replication entry
    if len(wanted_list) == 0:
        continue

    if known_latest_snapshot != '' and not resetonce:
        # Check if it matches remote snapshot
        rzfscmd = '"zfs list -Hr -o name -t snapshot -d 1 %s | tail -n 1 | cut -d@ -f2" || true' % (remotefs_final)
        sshproc = pipeopen('%s -p %d %s %s' % (sshcmd, remote_port, remote, rzfscmd))
        output = sshproc.communicate()[0]
        if output != '':
            expected_local_snapshot = '%s@%s' % (localfs, output.split('\n')[0])
            if expected_local_snapshot == last_snapshot:
                # Accept: remote and local snapshots matches
                log.debug("Found matching latest snapshot %s remotely" % (last_snapshot))
            elif expected_local_snapshot == known_latest_snapshot:
                # Accept
                log.debug("Found matching latest snapshot %s remotely (but not the recorded one)" % (known_latest_snapshot))
                last_snapshot = known_latest_snapshot
            else:
                # Do we have it locally? if yes then mark it immediately
                log.info("Can not locate expected snapshot %s, looking more carefully" % (expected_local_snapshot))
                MNTLOCK.lock()
                zfsproc = pipeopen('/sbin/zfs list -Ht snapshot -o name,freenas:state %s' % (expected_local_snapshot), debug)
                output = zfsproc.communicate()[0]
                if output != '':
                    last_snapshot, state = output.split('\n')[0].split('\t')
                    log.info("Marking %s as latest snapshot" % (last_snapshot))
                    if state == '-':
                        system('/sbin/zfs inherit freenas:state %s' % (known_latest_snapshot))
                        system('/sbin/zfs release -r freenas:repl %s' % (snapshot))
                        system('/sbin/zfs set freenas:state=LATEST %s' % (last_snapshot))
                        known_latest_snapshot = last_snapshot
                else:
                    log.warn("Can not locate a proper local snapshot for %s" % (localfs))
                    # Can NOT proceed any further.  Report this situation.
                    error, errmsg = send_mail(
                        subject="Replication failed! (%s)" % remote,
                        text="""
Hello,
    The replication failed for the local ZFS %s because the remote system
    has diverged snapshots with us.
                        """ % (localfs), interval=datetime.timedelta(hours=2), channel='autorepl')
                    MNTLOCK.unlock()
                    results[replication.id] = 'Remote system has diverged snapshots with us'
                    continue
                MNTLOCK.unlock()
        elif sshproc.returncode == 0:
            log.log(logging.NOTICE, "Can not locate %s on remote system, starting from there" % (known_latest_snapshot))
            # Reset the "latest" snapshot to a new one.
            system('/sbin/zfs set freenas:state=NEW %s' % (known_latest_snapshot))
            system('/sbin/zfs hold -r freenas:repl %s' % (known_latest_snapshot))
            wanted_list.insert(0, known_latest_snapshot)
            last_snapshot = ''
            known_latest_snapshot = ''
        else:
            log.warn("Got %d when running %s" % (sshproc.returncode, sshcmd))
            # Can NOT proceed any further.  Report this situation.
            error, errmsg = send_mail(subject="Replication failed!", text=\
                        """
Hello,
    The replication failed for the local ZFS %s because the command:
%s
    have returned an error code of %d
                        """ % (localfs, sshcmd, sshproc.returncode,), interval=datetime.timedelta(hours=2), channel='autorepl')
            results[replication.id] = 'SSH Failed'
            continue

    if resetonce:
        log.log(logging.NOTICE, "Destroying remote %s" % (remotefs_final))
        destroycmd = '%s -p %d %s /sbin/zfs destroy -rRf %s' % (sshcmd, remote_port, remote, remotefs_final)
        system(destroycmd)
        known_latest_snapshot = ''

    last_snapshot = known_latest_snapshot

    for snapname in wanted_list:
        local_fs, local_snap = snapname.split('@')
        if replication.repl_limit != 0:
            limit = '/usr/local/bin/throttle -K %d | ' % replication.repl_limit
        else:
            limit = ''
        cmd = ['/sbin/zfs', 'send', '-V']
        if replication.repl_userepl:
            cmd.append('-R')
        if last_snapshot == '':
            cmd.append(snapname)
        else:
            cmd.extend(['-I', last_snapshot, snapname])

        progressfile = '/tmp/.repl_progress_%d' % replication.id
        # subprocess.Popen does not handle large stream of data between
        # processes very well, do it on our own
        readfd, writefd = os.pipe()
        zproc_pid = os.fork()
        if zproc_pid == 0:
            os.close(readfd)
            os.dup2(writefd, 1)
            os.close(writefd)
            os.execv('/sbin/zfs', cmd)
            # NOTREACHED
        else:
            with open(progressfile, 'w') as f2:
                f2.write(str(zproc_pid))
            os.close(writefd)

        if compression == 'pigz':
            compress = '/usr/local/bin/pigz | '
            decompress = '/usr/local/bin/pigz -d | '
        elif compression == 'plzip':
            compress = '/usr/local/bin/plzip | '
            decompress = '/usr/local/bin/plzip -d | '
        elif compression == 'lz4':
            compress = '/usr/local/bin/lz4c | '
            decompress = '/usr/local/bin/lz4c -d | '
        else: #off
            compress = ''
            decompress = ''

        replcmd = '%s%s/bin/dd obs=1m 2> /dev/null | /bin/dd obs=1m 2> /dev/null | %s -p %d %s "%s/sbin/zfs receive -F -d %s && echo Succeeded"' % (compress, limit, sshcmd, remote_port, remote, decompress, remotefs)
        with open(templog, 'w+') as f:
            readobj = os.fdopen(readfd, 'r', 0)
            proc = subprocess.Popen(
                replcmd,
                shell=True,
                stdin=readobj,
                stdout=f,
                stderr=subprocess.STDOUT,
            )
            proc.wait()
            os.waitpid(zproc_pid, os.WNOHANG)
            readobj.close()
            os.remove(progressfile)
            f.seek(0)
            msg = f.read().strip('\n').strip('\r')
        os.remove(templog)
        log.debug("Replication result: %s" % (msg))
        msg = msg.replace('WARNING: enabled NONE cipher\n', '')
        results[replication.id] = msg

        # Determine if the remote side have the snapshot we have now.
        rzfscmd = '"zfs list -Hr -o name -t snapshot -d 1 %s | tail -n 1 | cut -d@ -f2"' % (remotefs_final)
        sshproc = pipeopen('%s -p %d %s %s' % (sshcmd, remote_port, remote, rzfscmd))
        output = sshproc.communicate()[0]
        if output != '':
            remote_snap = output.split('\n')[0]
            if local_snap == remote_snap:
                system('%s -p %d %s "/sbin/zfs inherit freenas:state %s@%s"' % (sshcmd, remote_port, remote, remotefs_final, remote_snap))
                # system('%s -p %d %s "/sbin/zfs hold -r freenas:repl %s@%s"' % (sshcmd, remote_port, remote, remotefs_final, remote_snap))
                # TODO: release all older snapshots
                # Replication was successful, mark as such
                MNTLOCK.lock()
                if last_snapshot != '':
                    system('/sbin/zfs inherit freenas:state %s' % (last_snapshot))
                    system('/sbin/zfs release -r freenas:repl %s' % (last_snapshot))
                last_snapshot = snapname
                system('/sbin/zfs set freenas:state=LATEST %s' % (last_snapshot))
                #
                # Place a hold.  This is harmless when it's already held but important if
                # there is no hold.
                #
                system('/sbin/zfs hold -r freenas:repl %s' % (last_snapshot))
                MNTLOCK.unlock()
                replication.repl_lastsnapshot = last_snapshot
                if resetonce:
                    replication.repl_resetonce = False
                replication.save()
                continue
            else:
                log.warn("Remote and local mismatch after replication: %s: local=%s vs remote=%s" % (local_fs, local_snap, remote_snap))
                rzfscmd = '"zfs list -Ho name -t snapshot -d 1 %s | tail -n 1 | cut -d@ -f2"' % (remotefs_final)
                sshproc = pipeopen('%s -p %d %s %s' % (sshcmd, remote_port, remote, rzfscmd))
                output = sshproc.communicate()[0]
                if output != '':
                    expected_local_snapshot = '%s@%s' % (localfs, output.split('\n')[0])
                    if expected_local_snapshot == snapname:
                        log.warn("Snapshot %s already exist on remote, marking as such" % (snapname))
                        system('%s -p %d %s "/sbin/zfs inherit -r freenas:state %s"' % (sshcmd, remote_port, remote, remotefs_final))
                        # Replication was successful, mark as such
                        MNTLOCK.lock()
                        system('/sbin/zfs inherit freenas:state %s' % (snapname))
                        system('/sbin/zfs release -r freenas:repl %s' % (snapname))
                        MNTLOCK.unlock()
                        continue

        # Something wrong, report.
        log.warn("Replication of %s failed with %s" % (snapname, msg))
        error, errmsg = send_mail(subject="Replication failed!", text=\
            """
Hello,
    The system was unable to replicate snapshot %s to %s
======================
%s
            """ % (localfs, remote, msg), interval=datetime.timedelta(hours=2), channel='autorepl')
        break

with open(REPL_RESULTFILE, 'w') as f:
    f.write(cPickle.dumps(results))
os.remove('/var/run/autorepl.pid')
log.debug("Autosnap replication finished")
