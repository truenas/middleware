#!/usr/bin/env python
#- 
# Copyright (c) 2011, 2012 iXsystems, Inc.
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
import sys
sys.path.append('/usr/local/www')
sys.path.append('/usr/local/www/freenasUI')

from freenasUI import settings

from django.core.management import setup_environ
setup_environ(settings)

from freenasUI.storage.models import Task, Replication
from datetime import datetime, time, timedelta

from freenasUI.common.pipesubr import pipeopen, system
from freenasUI.common.timesubr import isTimeBetween
from freenasUI.common.locks import mntlock

log = logging.getLogger('tools.autosnap')

# NOTE
#
# In this script there is no asynchnous programming so ALL locks are obtained
# in the blocking way.
#
# With this assumption, the mntlock SHOULD only be instansized once during the
# whole lifetime of this script.
#
MNTLOCK=mntlock()

# Set to True if verbose log desired
debug = False

def snapinfodict2datetime(snapinfo):
    year = int(snapinfo['year'])
    month = int(snapinfo['month'])
    day = int(snapinfo['day'])
    hour = int(snapinfo['hour'])
    minute = int(snapinfo['minute'])
    return datetime(year, month, day, hour, minute)

def snap_expired(snapinfo, snaptime):
    snapinfo_expirationtime = snapinfodict2datetime(snapinfo)
    snap_ttl_value = int(snapinfo['retcount'])
    snap_ttl_unit = snapinfo['retunit']

    if snap_ttl_unit == 'h':
        snapinfo_expirationtime = snapinfo_expirationtime + timedelta(hours = snap_ttl_value)
    elif snap_ttl_unit == 'd':
        snapinfo_expirationtime = snapinfo_expirationtime + timedelta(days = snap_ttl_value)
    elif snap_ttl_unit == 'w':
        snapinfo_expirationtime = snapinfo_expirationtime + timedelta(days = 7*snap_ttl_value)
    elif snap_ttl_unit == 'm':
        snapinfo_expirationtime = snapinfo_expirationtime + timedelta(days = int(30.436875*snap_ttl_value))
    elif snap_ttl_unit == 'y':
        snapinfo_expirationtime = snapinfo_expirationtime + timedelta(days = int(365.2425*snap_ttl_value))

    return snapinfo_expirationtime <= snaptime

def isMatchingTime(task, snaptime):
    curtime = time(snaptime.hour, snaptime.minute)
    repeat_type = task.task_repeat_unit

    if not isTimeBetween(curtime, task.task_begin, task.task_end):
        return False

    if repeat_type == 'daily':
        return True

    if repeat_type == 'weekly':
        cur_weekday = snaptime.weekday() + 1
        if ('%d' % cur_weekday) in task.task_byweekday.split(','):
            return True

    return False

# Detect if another instance is running
def exit_if_running(pid):
    log.debug("Checking if process %d is still alive", pid)
    try:
        os.kill(pid, 0)
        # If we reached here, there is another process in progress
        log.debug("Process %d still working, quitting", pid)
        sys.exit(0)
    except OSError:
        log.debug("Process %d gone", pid)

mypid = os.getpid()

# (mis)use MNTLOCK as PIDFILE lock.
locked = True
try:
    MNTLOCK.lock_try()
except IOError:
    locked = False
if not locked:
    sys.exit(0)

AUTOSNAP_PID = -1
try:
    with open('/var/run/autosnap.pid') as pidfile:
        AUTOSNAP_PID = int(pidfile.read())
except:
    pass

if AUTOSNAP_PID != -1:
    exit_if_running(AUTOSNAP_PID)

with open('/var/run/autosnap.pid', 'w') as pidfile:
    pidfile.write('%d' % mypid)

MNTLOCK.unlock()

now = datetime.now().replace(microsecond=0)
if now.second < 30 or now.minute == 59:
    snaptime = now.replace(second=0)
else:
    snaptime = now.replace(minute=now.minute + 1, second=0)

mp_to_task_map = {}

# Grab all matching tasks into a tree.
# Since the snapshot we make have the name 'foo@auto-%Y%m%d.%H%M-{expire time}'
# format, we just keep one task.
TaskObjects = Task.objects.filter(task_enabled=True)
for task in TaskObjects:
    if isMatchingTime(task, snaptime):
        fs = task.task_filesystem
        expire_time = ('%s%s' % (task.task_ret_count, task.task_ret_unit[0])).__str__()
        tasklist = []
        if mp_to_task_map.has_key((fs, expire_time)):
            tasklist = mp_to_task_map[(fs, expire_time)]
            tasklist.append(task)
        else:
            tasklist = [task]
        mp_to_task_map[(fs, expire_time)] = tasklist

# Do not proceed further if we are not going to generate any snapshots for this run
if len(mp_to_task_map) == 0:
    exit()

# Grab all existing snapshot and filter out the expiring ones
snapshots = {}
snapshots_pending_delete = set()
zfsproc = pipeopen("/sbin/zfs list -t snapshot -H", debug, logger=log)
lines = zfsproc.communicate()[0].split('\n')
reg_autosnap = re.compile('^auto-(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2}).(?P<hour>\d{2})(?P<minute>\d{2})-(?P<retcount>\d+)(?P<retunit>[hdwmy])$')
for line in lines:
    if line != '':
        snapshot_name = line.split('\t')[0]
        fs, snapname = snapshot_name.split('@')
        snapname_match = reg_autosnap.match(snapname)
        if snapname_match != None:
            snap_infodict = snapname_match.groupdict()
            snap_ret_policy = '%s%s' % (snap_infodict['retcount'], snap_infodict['retunit'])
            if snap_expired(snap_infodict, snaptime):
                snapshots_pending_delete.add(snapshot_name)
            else:
                if mp_to_task_map.has_key((fs, snap_ret_policy)):
                    if snapshots.has_key((fs, snap_ret_policy)):
                        last_snapinfo = snapshots[(fs, snap_ret_policy)]
                        if snapinfodict2datetime(last_snapinfo) < snapinfodict2datetime(snap_infodict):
                            snapshots[(fs, snap_ret_policy)] = snap_infodict
                    else:
                        snapshots[(fs, snap_ret_policy)] = snap_infodict

list_mp = mp_to_task_map.keys()

for mpkey in list_mp:
    tasklist = mp_to_task_map[mpkey]
    if snapshots.has_key(mpkey):
        snapshot_time = snapinfodict2datetime(snapshots[mpkey])
        for taskindex in range(len(tasklist) -1, -1, -1):
            task = tasklist[taskindex]
            if snapshot_time + timedelta(minutes = task.task_interval) > snaptime:
                del tasklist[taskindex]
        if len(tasklist) == 0:
            del mp_to_task_map[mpkey]

snaptime_str = snaptime.strftime('%Y%m%d.%H%M')

for mpkey, tasklist in mp_to_task_map.items():
    fs, expire = mpkey
    recursive = False
    for task in tasklist:
        if task.task_recursive == True:
            recursive = True
    if recursive == True:
        rflag = ' -r'
    else:
        rflag = ''

    snapname = '%s@auto-%s-%s' % (fs, snaptime_str, expire)

    # If there is associated replication task, mark the snapshots as 'NEW'.
    if Replication.objects.filter(repl_filesystem=fs, repl_enabled=True).count() > 0:
        MNTLOCK.lock()
        snapcmd = '/sbin/zfs snapshot%s -o freenas:state=NEW %s' % (rflag, snapname)
        proc = pipeopen(snapcmd, logger=log)
        err = proc.communicate()[1]
        if proc.returncode != 0:
            log.error("Failed to create snapshot '%s': %s", snapname, err)
        MNTLOCK.unlock()
    else:
        snapcmd = '/sbin/zfs snapshot%s %s' % (rflag, snapname)
        proc = pipeopen(snapcmd, logger=log)
        err = proc.communicate()[1]
        if proc.returncode != 0:
            log.error("Failed to create snapshot '%s': %s", snapname, err)

MNTLOCK.lock()
for snapshot in snapshots_pending_delete:
    zfsproc = pipeopen('/sbin/zfs get -H freenas:state %s' % (snapshot, ), logger=log)
    output = zfsproc.communicate()[0]
    if output != '':
        fsname, attrname, value, source = output.split('\n')[0].split('\t')
        if value == '-':
            snapcmd = '/sbin/zfs destroy -r -d %s' % (snapshot) #snapshots with clones will have destruction deferred
            proc = pipeopen(snapcmd, logger=log)
            err = proc.communicate()[1]
            if proc.returncode != 0:
                log.error("Failed to destroy snapshot '%s': %s", snapshot, err)

os.unlink('/var/run/autosnap.pid')
MNTLOCK.unlock()

os.execl('/usr/local/bin/python',
         'python',
         '/usr/local/www/freenasUI/tools/autorepl.py')
