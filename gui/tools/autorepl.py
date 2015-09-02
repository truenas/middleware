#!/usr/bin/env python
#-
# Copyright (c) 2011, 2015 iXsystems, Inc.
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
import re
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

#
# Parse a list of 'zfs list -H -t snapshot -p -o name,creation' output
# and place the result in a map of dataset name to a list of snapshot
# name and timestamp.
#
def mapfromdata(input):
    m = {}
    for line in input:
        if line == '':
            continue
        snapname, timestamp = line.split('\t')
        dataset, snapname = snapname.split('@')
        if m.has_key(dataset):
            m[dataset].append((snapname, timestamp))
        else:
            m[dataset] = [(snapname, timestamp)]
    return m

#
# Return a pair of compression and decompress pipe commands
#
map_compression = {
    'pigz': ('/usr/local/bin/pigz', '/usr/local/bin/pigz -d'),
    'plzip': ('/usr/local/bin/plzip', '/usr/local/bin/plzip -d'),
    'lz4': ('/usr/local/bin/lz4c', '/usr/local/bin/lz4c -d'),
    'xz': ('/usr/bin/xz', '/usr/bin/xzdec'),
}

def compress_pipecmds(compression):
    if map_compression.has_key(compression):
        compress, decompress = map_compression[compression]
        compress = compress + ' | '
        decompress = decompress + ' | '
    else:
        compress = ''
        decompress = ''
    return (compress, decompress)

#
# Attempt to send a snapshot or increamental stream to remote.
#
def sendzfs(fromsnap, tosnap, dataset, localfs, remotefs, throttle, replication):
    global results
    global templog

    progressfile = '/tmp/.repl_progress_%d' % replication.id
    cmd = ['/sbin/zfs', 'send', '-V']
    if fromsnap is None:
        cmd.append("%s@%s" % (dataset, tosnap))
    else:
        cmd.extend(['-i', "%s@%s" % (dataset, fromsnap), "%s@%s" % (dataset, tosnap)])
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

    compress, decompress = compress_pipecmds(replication.repl_compression.__str__())

    replcmd = '%s%s/bin/dd obs=1m 2> /dev/null | /bin/dd obs=1m 2> /dev/null | %s "%s/sbin/zfs receive -F -d \'%s\' && echo Succeeded"' % (compress, throttle, sshcmd, decompress, remotefs)
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
    msg = msg.replace('WARNING: enabled NONE cipher\n', '')
    log.debug("Replication result: %s" % (msg))
    results[replication.id] = msg
    return (msg == "Succeeded")

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

system_re = re.compile('^[^/]+/.system.*')

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

    if replication.repl_limit != 0:
        throttle = '/usr/local/bin/throttle -K %d | ' % replication.repl_limit
    else:
        throttle = ''

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

    sshcmd = '%s -p %d %s' % (sshcmd, remote_port, remote)


    if replication.repl_userepl:
        Rflag = '-R '
    else:
        Rflag = ''

    # For now, use 'recurse' flag as followdelete flag
    followdelete = not not replication.repl_userepl

    wanted_list = []
    known_latest_snapshot = ''
    expected_local_snapshot = ''

    remotefs_final = "%s%s%s" % (remotefs, localfs.partition('/')[1],localfs.partition('/')[2])

    # Examine local list of snapshots, then remote snapshots, and determine if there is any work to do.
    log.debug("Checking dataset %s" % (localfs))

    # Grab map from local system.
    if replication.repl_userepl:
        zfsproc = pipeopen('/sbin/zfs list -H -t snapshot -p -o name,creation -r "%s"' % (localfs), debug)
    else:
        zfsproc = pipeopen('/sbin/zfs list -H -t snapshot -p -o name,creation -r -d 1 "%s"' % (localfs), debug)

    output, error = zfsproc.communicate()
    if zfsproc.returncode:
        log.warn('Could not determine last available snapshot for dataset %s: %s' % (
            localfs,
            error,
            ))
        MNTLOCK.unlock()
        continue
    if output != '':
        snaplist = output.split('\n')
        snaplist = [x for x in snaplist if not system_re.match(x)]
        map_source = mapfromdata(snaplist)

    # Grab map from remote system
    if replication.repl_userepl:
        rzfscmd = '"zfs list -H -t snapshot -p -o name,creation -r \'%s\'"' % (remotefs_final)
    else:
        rzfscmd = '"zfs list -H -t snapshot -p -o name,creation -d 1 -r \'%s\'"' % (remotefs_final)
    sshproc = pipeopen('%s %s' % (sshcmd, rzfscmd))
    output = sshproc.communicate()[0]
    if output != '':
        snaplist = output.split('\n')
        snaplist = [x for x in snaplist if not system_re.match(x) and x != '']
        # Process snaplist so that it matches the desired form of source side
        l = len(remotefs_final)
        snaplist = [ localfs + x[l:] for x in snaplist ]
        map_target = mapfromdata(snaplist)
    else:
        map_target = {}

    tasks = {}
    delete_tasks = {}

    # Now we have map_source and map_target, which would be used to calculate the replication
    # path from source to target.
    for dataset in map_source:
        if map_target.has_key(dataset):
            # Find out the last common snapshot.
            #
            # We have two ordered lists, list_source and list_target
            # which are ordered by the creation time.  Because they
            # are ordered, we can have two pointers and scan backward
            # until we hit one identical item, or hit the end of
            # either list.
            list_source = map_source[dataset]
            list_target = map_target[dataset]
            i = len(list_source) - 1
            j = len(list_target) - 1
            sourcesnap, sourcetime = list_source[i]
            targetsnap, targettime = list_target[j]
            while i >= 0 and j >= 0:
                # found.
                if sourcesnap == targetsnap and sourcetime == targettime:
                    break
                elif sourcetime > targettime:
                    i-=1
                    if i < 0:
                        break
                    sourcesnap, sourcetime = list_source[i]
                else:
                    j-=1
                    if j < 0:
                        break
                    targetsnap, targettime = list_target[j]
            if sourcesnap == targetsnap and sourcetime == targettime:
                # found: i, j points to the right position.
                # we do not care much if j is pointing to the last snapshot
                # if source side have new snapshot(s), report it.
                if i < len(list_source) - 1:
                    tasks[dataset] = [ m[0] for m in list_source[i:] ]
                if followdelete:
                    # All snapshots that do not exist on the source side should
                    # be deleted when followdelete is requested.
                    delete_set = set([ m[0] for m in list_target]) - set([ m[0] for m in list_source])
                    if len(delete_set) > 0:
                        delete_tasks[dataset] = delete_set
            else:
                # no identical snapshot found, nuke and repave.
                tasks[dataset] = [None] + [ m[0] for m in list_source[i:] ]
        else:
            # New dataset on source side: replicate to the target.
            tasks[dataset] = [None] + [ m[0] for m in map_source[dataset] ]

    # Removed dataset(s)
    for dataset in map_target:
        if not map_source.has_key(dataset):
            tasks[dataset] = [map_target[dataset][-1][0], None]

    previously_deleted = "/"
    l = len(localfs)
    for dataset in sorted(tasks.keys()):
        tasklist = tasks[dataset]
        if tasklist[0] == None:
            # No matching snapshot(s) exist.  If there is any snapshots on the
            # target side, destroy all existing snapshots so we can proceed.
            if map_target.has_key(dataset):
                list_target = map_target[dataset]
                snaplist = [ remotefs_final + dataset[l:] + '@' + x[0] for x in list_target ]
                failed_snapshots = []
                for snapshot in snaplist:
                    rzfscmd = '"zfs destroy \'%s\'"' % (snapshot)
                    sshproc = pipeopen('%s %s' % (sshcmd, rzfscmd))
                    output, error = sshproc.communicate()
                    if sshproc.returncode:
                        log.warn("Unable to destroy snapshot %s on remote system" % (snapshot))
                        failed_snapshots.append(snapshot)
                if len(failed_snapshots) > 0:
                    # We can't proceed in this situation, report
                    error, errmsg = send_mail(
                        subject="Replication failed! (%s)" % remote,
                        text="""
Hello,
    The replication failed for the local ZFS %s because the remote system
    has diverged snapshots with us and we were unable to remove them,
    including:
%s
                        """ % (localfs, failed_snapshots), interval=datetime.timedelta(hours=2), channel='autorepl')
                    results[replication.id] = 'Unable to destroy remote snapshot: %s' % (failed_snapshots)
                    ### rzfs destroy %s
            psnap = tasklist[1]
            success = sendzfs(None, psnap, dataset, localfs, remotefs, throttle, replication)
            if success:
                for nsnap in tasklist[2:]:
                    success = sendzfs(psnap, nsnap, dataset, localfs, remotefs, throttle, replication)
                    if not success:
                        # Report the situation
                        error, errmsg = send_mail(
                            subject="Replication failed at %s@%s -> %s" % (dataset, psnap, nsnap),
                            text="""
Hello,
    The replication failed for the local ZFS %s while attempting to
    apply incremental send of snapshot %s -> %s to %s
                            """ % (dataset, psnap, nsnap, remote), interval=datetime.timedelta(hours=2), channel='autorepl')
                        results[replication.id] = 'Failed: %s (%s->%s)' % (dataset, psnap, nsnap)
                        break
                    psnap = nsnap
            else:
                # Report the situation
                error, errmsg = send_mail(
                    subject="Replication failed when sending %s@%s" % (dataset, psnap),
                    text="""
Hello,
    The replication failed for the local ZFS %s while attempting to
    send snapshot %s to %s
                    """ % (dataset, psnap, remote), interval=datetime.timedelta(hours=2), channel='autorepl')
                results[replication.id] = 'Failed: %s (%s)' % (dataset, psnap)
                continue
        elif tasklist[1] != None:
            psnap = tasklist[0]
            allsucceeded = True
            for nsnap in tasklist[1:]:
                success = sendzfs(psnap, nsnap, dataset, localfs, remotefs, throttle, replication)
                allsucceeded = allsucceeded and success
                if not success:
                    # Report the situation
                    error, errmsg = send_mail(
                        subject="Replication failed at %s@%s -> %s" % (dataset, psnap, nsnap),
                        text="""
Hello,
    The replication failed for the local ZFS %s while attempting to
    apply incremental send of snapshot %s -> %s to %s
                        """ % (dataset, psnap, nsnap, remote), interval=datetime.timedelta(hours=2), channel='autorepl')
                    results[replication.id] = 'Failed: %s (%s->%s)' % (dataset, psnap, nsnap)
                    break
                psnap = nsnap
            if allsucceeded and delete_tasks.has_key(dataset):
                zfsname = remotefs_final + dataset[l:]
                for snapshot in delete_tasks[dataset]:
                    rzfscmd = '"zfs destroy -d \'%s@%s\'"' % (zfsname, snapshot)
                    sshproc = pipeopen('%s %s' % (sshcmd, rzfscmd))
                    sshproc.communicate()
        else:
            # Remove the named dataset.
            zfsname = remotefs_final + dataset[l:]
            if zfsname.startswith(previously_deleted):
                continue
            else:
                rzfscmd = '"zfs destroy -r \'%s\'"' % (zfsname)
                sshproc = pipeopen('%s %s' % (sshcmd, rzfscmd))
                output, error = sshproc.communicate()
                if sshproc.returncode:
                    log.warn("Unable to destroy dataset %s on remote system" % (zfsname))
                else:
                    previously_deleted = zfsname

with open(REPL_RESULTFILE, 'w') as f:
    f.write(cPickle.dumps(results))
os.remove('/var/run/autorepl.pid')
log.debug("Autosnap replication finished")
