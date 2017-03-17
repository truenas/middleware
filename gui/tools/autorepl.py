#!/usr/bin/env python
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

import pickle
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

import django
django.setup()

from freenasUI.freeadmin.apppool import appPool
from freenasUI.storage.models import Replication, REPL_RESULTFILE
from freenasUI.common.timesubr import isTimeBetween
from freenasUI.common.pipesubr import pipeopen
from freenasUI.common.locks import mntlock
from freenasUI.common.system import send_mail, get_sw_name


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
        if dataset in m:
            m[dataset].append((snapname, timestamp))
        else:
            m[dataset] = [(snapname, timestamp)]
    return m

#
# Return a pair of compression and decompress pipe commands
#
map_compression = {
    'pigz': ('/usr/local/bin/pigz', '/usr/bin/env pigz -d'),
    'plzip': ('/usr/local/bin/plzip', '/usr/bin/env plzip -d'),
    'lz4': ('/usr/local/bin/lz4c', '/usr/bin/env lz4c -d'),
    'xz': ('/usr/bin/xz', '/usr/bin/env xzdec'),
}

is_truenas = not (get_sw_name().lower() == 'freenas')


def compress_pipecmds(compression):
    if compression in map_compression:
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
def sendzfs(fromsnap, tosnap, dataset, localfs, remotefs, followdelete, throttle, compression, replication, reached_last):
    global results
    global templog

    progressfile = '/tmp/.repl_progress_%d' % replication.id
    cmd = ['/sbin/zfs', 'send', '-V']

    # -p switch will send properties for whole dataset, including snapshots
    # which will result in stale snapshots being delete as well
    if followdelete:
        cmd.append('-p')

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

    compress, decompress = compress_pipecmds(compression)
    replcmd = '%s%s/bin/dd obs=1m 2> /dev/null | /bin/dd obs=1m 2> /dev/null | /usr/local/bin/pipewatcher $$ | %s "%s/sbin/zfs receive -F -d \'%s\' && echo Succeeded"' % (compress, throttle, sshcmd, decompress, remotefs)
    log.debug('Sending zfs snapshot: %s | %s', ' '.join(cmd), replcmd)
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
    msg = msg.replace('WARNING: ENABLED NONE CIPHER', '')
    msg = msg.strip('\r').strip('\n')
    log.debug("Replication result: %s" % (msg))
    results[replication.id] = msg
    # When replicating to a target "container" dataset that doesn't exist on the sending
    # side the target dataset will have to be readonly, however that will preclude
    # creating mountpoints for the datasets that are sent.
    # In that case you'll get back a failed to create mountpoint message, which
    # we'll go ahead and consider a success.
    if reached_last and ("Succeeded" in msg or "failed to create mountpoint" in msg):
        replication.repl_lastsnapshot = tosnap
        # Re-query replication to update field because replication settings
        # might have been updated while this script was running
        Replication.objects.filter(id=replication.id).update(
            repl_lastsnapshot=tosnap
        )
    return ("Succeeded" in msg or "failed to create mountpoint" in msg)

log = logging.getLogger('tools.autorepl')

# Set to True if verbose log desired
debug = False


# Detect if another instance is running
def exit_if_running(pid):
    if 'AUTOREPL_SKIP_RUNNING' in os.environ:
        log.debug('Skipping check if autorepl is running.')
        return
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

start = datetime.datetime.now().replace(microsecond=0)
if start.second < 30 or start.minute == 59:
    now = start.replace(second=0)
else:
    now = start.replace(minute=start.minute + 1, second=0)
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
    results = pickle.loads(data)
except:
    results = {}


def write_results():
    global results
    with open(REPL_RESULTFILE, 'w') as f:
        f.write(pickle.dumps(results))

system_re = re.compile('^[^/]+/.system.*')

# Traverse all replication tasks
replication_tasks = Replication.objects.all()
for replication in replication_tasks:
    if not isTimeBetween(now, replication.repl_begin, replication.repl_end):
        continue

    if not replication.repl_enabled:
        log.debug("%s replication not enabled" % replication)
        continue

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

    if replication.repl_limit != 0:
        throttle = '/usr/local/bin/throttle -K %d | ' % replication.repl_limit
    else:
        throttle = ''

    if cipher == 'fast':
        sshcmd = (
            '/usr/local/bin/ssh -c arcfour256,arcfour128,blowfish-cbc,'
            'aes128-ctr,aes192-ctr,aes256-ctr -i /data/ssh/replication'
            ' -o BatchMode=yes -o StrictHostKeyChecking=yes'
            # There's nothing magical about ConnectTimeout, it's an average
            # of wiliam and josh's thoughts on a Wednesday morning.
            # It will prevent hunging in the status of "Sending".
            ' -o ConnectTimeout=7'
        )
    elif cipher == 'disabled':
        sshcmd = ('/usr/local/bin/ssh -ononeenabled=yes -ononeswitch=yes -i /data/ssh/replication -o BatchMode=yes'
                  ' -o StrictHostKeyChecking=yes'
                  ' -o ConnectTimeout=7')
    else:
        sshcmd = ('/usr/local/bin/ssh -i /data/ssh/replication -o BatchMode=yes'
                  ' -o StrictHostKeyChecking=yes'
                  ' -o ConnectTimeout=7')

    if dedicateduser:
        sshcmd = "%s -l %s" % (sshcmd, dedicateduser.encode('utf-8'))

    sshcmd = '%s -p %d %s' % (sshcmd, remote_port, remote)

    remotefs_final = "%s%s%s" % (remotefs, localfs.partition('/')[1], localfs.partition('/')[2])

    # Examine local list of snapshots, then remote snapshots, and determine if there is any work to do.
    log.debug("Checking dataset %s" % (localfs))

    # Grab map from local system.
    if recursive:
        zfsproc = pipeopen('/sbin/zfs list -H -t snapshot -p -o name,creation -r "%s"' % (localfs), debug)
    else:
        zfsproc = pipeopen('/sbin/zfs list -H -t snapshot -p -o name,creation -r -d 1 "%s"' % (localfs), debug)

    output, error = zfsproc.communicate()
    if zfsproc.returncode:
        log.warn('Could not determine last available snapshot for dataset %s: %s' % (
            localfs,
            error,
        ))
        continue
    if output != '':
        snaplist = output.split('\n')
        snaplist = [x for x in snaplist if not system_re.match(x)]
        map_source = mapfromdata(snaplist)

    rzfscmd = '"zfs list -H -o name,readonly -t filesystem,volume -r %s"' % (remotefs_final.split('/')[0])
    sshproc = pipeopen('%s %s' % (sshcmd, rzfscmd))
    output, error = sshproc.communicate()
    remote_zfslist = {}
    for i in re.sub(r'[ \t]+', ' ', output, flags=re.M).splitlines():
        data = i.split()
        remote_zfslist[data[0]] = {'readonly': data[1] == 'on'}

    # Attempt to create the remote dataset.  If it fails, we don't care at this point.
    rzfscmd = "zfs create -o readonly=on "
    ds = ''
    if "/" not in localfs:
        localfs_tmp = "%s/%s" % (localfs, localfs)
    else:
        localfs_tmp = localfs
    for dir in (remotefs.partition("/")[2] + "/" + localfs_tmp.partition("/")[2]).split("/"):
        # If this test fails there is no need to create datasets on the remote side
        # eg: tank -> tank replication
        if '/' in remotefs or '/' in localfs:
            ds = os.path.join(ds, dir)
            ds_full = '%s/%s' % (remotefs.split('/')[0], ds)
            if ds_full in remote_zfslist:
                continue
            log.debug("ds = %s, remotefs = %s" % (ds, remotefs))
            sshproc = pipeopen('%s %s %s' % (sshcmd, rzfscmd, ds_full), quiet=True)
            output, error = sshproc.communicate()
            error = error.strip('\n').strip('\r').replace('WARNING: ENABLED NONE CIPHER', '')
            # Debugging code
            if sshproc.returncode:
                log.debug("Unable to create remote dataset %s: %s" % (
                    remotefs,
                    error
                ))

    if is_truenas:
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
        error = error.strip('\n').strip('\r').replace('WARNING: ENABLED NONE CIPHER', '')
        if sshproc.returncode:
            # Be conservative: only consider it's Okay when we see the expected result.
            if error != '':
                if error.split('\n')[0] == ("cannot open '%s': dataset does not exist" % (remotefs_final)):
                    may_proceed = True
        else:
            if output != '':
                if output.find('off') == -1:
                    may_proceed = True
        if not may_proceed:
            # Report the problem and continue
            results[replication.id] = 'Remote destination must be set readonly'
            log.debug("dataset %s and it's children must be readonly." % remotefs_final)
            if ("on" in output or "off" in output) and len(output) > 0:
                error, errmsg = send_mail(
                    subject="Replication denied! (%s)" % remote,
                    text="""
Hello,
    The remote system have denied our replication from local ZFS
    %s to remote ZFS %s.  Please change the 'readonly' property
    of:
        %s
    as well as its children to 'on' to allow receiving replication.
                    """ % (localfs, remotefs_final, remotefs_final), interval=datetime.timedelta(hours=24), channel='autorepl')
            else:
                if len(output) > 0:
                    error, errmsg = send_mail(
                            subject="Replication failed! (%s)" % remote,
                            text="""
Hello,
    Replication of local ZFS %s to remote ZFS %s failed.""" % (localfs, remotefs_final), interval=datetime.timedelta(hours=24), channel='autorepl')
                    results[replication.id] = 'Remote system denied receiving of snapshot on %s' % (remotefs_final)
                else:
                    error, errmsg = send_mail(
                            subject="Replication failed! (%s)" % remote,
                            text="""
Hello,
    Replication of local ZFS %s to remote ZFS %s failed.  The remote system is not responding.""" % (localfs, remotefs_final), interval=datetime.timedelta(hours=24), channel='autorepl')
                    results[replication.id] = 'Remote system not responding.'
            continue

    # Remote filesystem is the root dataset
    # Make sure it has no .system dataset over there because zfs receive will try to
    # remove it and fail (because its mounted and being used)
    if '/' not in remotefs_final:
        rzfscmd = '"mount | grep ^%s/.system"' % (remotefs_final)
        sshproc = pipeopen('%s %s' % (sshcmd, rzfscmd), debug)
        output = sshproc.communicate()[0].strip()
        if output != '':
            results[replication.id] = 'Please move system dataset of remote side to another pool'
            continue

    # Grab map from remote system
    if recursive:
        rzfscmd = '"zfs list -H -t snapshot -p -o name,creation -r \'%s\'"' % (remotefs_final)
    else:
        rzfscmd = '"zfs list -H -t snapshot -p -o name,creation -d 1 -r \'%s\'"' % (remotefs_final)
    sshproc = pipeopen('%s %s' % (sshcmd, rzfscmd), debug)
    output, error = sshproc.communicate()
    error = error.strip('\n').strip('\r').replace('WARNING: ENABLED NONE CIPHER', '')
    if output != '':
        snaplist = output.split('\n')
        snaplist = [x for x in snaplist if not system_re.match(x) and x != '']
        # Process snaplist so that it matches the desired form of source side
        l = len(remotefs_final)
        snaplist = [localfs + x[l:] for x in snaplist]
        map_target = mapfromdata(snaplist)
    elif error != '':
        results[replication.id] = 'Failed: %s' % (error)
        continue
    else:
        map_target = {}

    tasks = {}
    delete_tasks = {}

    # Now we have map_source and map_target, which would be used to calculate the replication
    # path from source to target.
    for dataset in map_source:
        if dataset in map_target:
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
                    i -= 1
                    if i < 0:
                        break
                    sourcesnap, sourcetime = list_source[i]
                else:
                    j -= 1
                    if j < 0:
                        break
                    targetsnap, targettime = list_target[j]
            if sourcesnap == targetsnap and sourcetime == targettime:
                # found: i, j points to the right position.
                # we do not care much if j is pointing to the last snapshot
                # if source side have new snapshot(s), report it.
                if i < len(list_source) - 1:
                    tasks[dataset] = [m[0] for m in list_source[i:]]
                if followdelete:
                    # All snapshots that do not exist on the source side should
                    # be deleted when followdelete is requested.
                    delete_set = set([m[0] for m in list_target]) - set([m[0] for m in list_source])
                    if len(delete_set) > 0:
                        delete_tasks[dataset] = delete_set
            else:
                # no identical snapshot found, nuke and repave.
                tasks[dataset] = [None] + [m[0] for m in list_source[i:]]
        else:
            # New dataset on source side: replicate to the target.
            tasks[dataset] = [None] + [m[0] for m in map_source[dataset]]

    # Removed dataset(s)
    for dataset in map_target:
        if dataset not in map_source:
            tasks[dataset] = [map_target[dataset][-1][0], None]

    previously_deleted = "/"
    l = len(localfs)
    total_datasets = len(list(tasks.keys()))
    if total_datasets == 0:
        results[replication.id] = 'Up to date'
        write_results()
        continue
    current_dataset = 0

    results[replication.id] = 'Running'
    write_results()

    # Go through datasets in reverse order by level in hierarchy
    # This is because in case datasets being remounted we need to make sure
    # tank/foo is mounted after tank/foo/bar and the latter does not get hidden.
    # See #12455
    for dataset in sorted(list(tasks.keys()), key=lambda y: len(y.split('/')), reverse=True):
        tasklist = tasks[dataset]
        current_dataset += 1
        reached_last = (current_dataset == total_datasets)
        if tasklist[0] is None:
            # No matching snapshot(s) exist.  If there is any snapshots on the
            # target side, destroy all existing snapshots so we can proceed.
            if dataset in map_target:
                list_target = map_target[dataset]
                snaplist = [remotefs_final + dataset[l:] + '@' + x[0] for x in list_target]
                failed_snapshots = []
                log.debug('Deleting %d snapshot(s) in pull side because not a single matching snapshot was found', len(snaplist))
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
                    # ## rzfs destroy %s
            psnap = tasklist[1]
            success = sendzfs(None, psnap, dataset, localfs, remotefs, followdelete, throttle, compression, replication, reached_last)
            if success:
                for nsnap in tasklist[2:]:
                    success = sendzfs(psnap, nsnap, dataset, localfs, remotefs, followdelete, throttle, compression, replication, reached_last)
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
        elif tasklist[1] is not None:
            psnap = tasklist[0]
            allsucceeded = True
            for nsnap in tasklist[1:]:
                success = sendzfs(psnap, nsnap, dataset, localfs, remotefs, followdelete, throttle, compression, replication, reached_last)
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
            if allsucceeded and dataset in delete_tasks:
                zfsname = remotefs_final + dataset[l:]
                log.debug('Deleting %d stale snapshot(s) on pull side', len(delete_tasks[dataset]))
                for snapshot in delete_tasks[dataset]:
                    rzfscmd = '"zfs destroy -d \'%s@%s\'"' % (zfsname, snapshot)
                    sshproc = pipeopen('%s %s' % (sshcmd, rzfscmd))
                    sshproc.communicate()
            if allsucceeded:
                    results[replication.id] = 'Succeeded'
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

write_results()

end = datetime.datetime.now().replace(microsecond=0)
# In case this script took longer than 5 minutes to run and a successful
# replication happened, lets re-run it to prevent periodic snapshots to be
# deleted prior to be replicated (this might happen when its the first snapshot
# being sent and it takes longer than the snapshots retention time.
if (end - start).total_seconds() > 300:
    log.debug('Relaunching autorepl')
    os.environ['AUTOREPL_SKIP_RUNNING'] = '1'
    os.execl(
        '/usr/local/bin/python',
        'python',
        '/usr/local/www/freenasUI/tools/autorepl.py'
    )


os.remove('/var/run/autorepl.pid')
log.debug("Autosnap replication finished")
