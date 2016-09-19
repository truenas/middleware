#!/usr/bin/env python
#
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

import cPickle as pickle
import logging
import os
import re
import sys
import uuid
import ssl

from pysphere import VIServer

# Monkey patch ssl checking to get back to Python 2.7.8 behavior
ssl._create_default_https_context = ssl._create_unverified_context

sys.path.append('/usr/local/www')
sys.path.append('/usr/local/www/freenasUI')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')

# Make sure to load all modules
from django.db.models.loading import cache
cache.get_apps()

from freenasUI.freeadmin.apppool import appPool
from freenasUI.storage.models import Task
from datetime import datetime, time, timedelta

from freenasUI.common.locks import mntlock
from freenasUI.common.pipesubr import pipeopen
from freenasUI.common.system import send_mail
from freenasUI.common.timesubr import isTimeBetween
from freenasUI.storage.models import VMWarePlugin

from lockfile import LockFile

# setup ability to log to syslog
logging.NOTICE = 60
logging.addLevelName(logging.NOTICE, "NOTICE")
log = logging.getLogger('tools.autosnap')

# NOTE
#
# In this script there is no asynchnous programming so ALL locks are obtained
# in the blocking way.
#
# With this assumption, the mntlock SHOULD only be instansized once during the
# whole lifetime of this script.
#
MNTLOCK = mntlock()

VMWARE_FAILS = '/var/tmp/.vmwaresnap_fails'
VMWARESNAPDELETE_FAILS = '/var/tmp/.vmwaresnapdelete_fails'

# Set to True if verbose log desired
# TODO: Most of the debug has left the building over the years
# Make debug output great again.
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
        snapinfo_expirationtime = snapinfo_expirationtime + timedelta(hours=snap_ttl_value)
    elif snap_ttl_unit == 'd':
        snapinfo_expirationtime = snapinfo_expirationtime + timedelta(days=snap_ttl_value)
    elif snap_ttl_unit == 'w':
        snapinfo_expirationtime = snapinfo_expirationtime + timedelta(days=7 * snap_ttl_value)
    elif snap_ttl_unit == 'm':
        snapinfo_expirationtime = snapinfo_expirationtime + timedelta(days=int(30.436875 * snap_ttl_value))
    elif snap_ttl_unit == 'y':
        snapinfo_expirationtime = snapinfo_expirationtime + timedelta(days=int(365.2425 * snap_ttl_value))

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


def autorepl_running():
    if not os.path.exists('/var/run/autorepl.pid'):
        return False
    with open('/var/run/autorepl.pid', 'r') as f:
        pid = f.read().strip('\n')
    if not pid.isdigit():
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


# Check if a VM is using a certain datastore
def doesVMDependOnDataStore(vm, dataStore):
    try:
        # simple case, VM config data is on a datastore.
        # not sure how critical it is to snapshot the store that has config data, but best to do so
        if vm.get_property('path').startswith("[%s]" % dataStore):
            return True
        # check if VM has disks on the data store
        # we check both "diskDescriptor" and "diskExtent" types of files
        disks = vm.get_property("disks")
        for disk in disks:
            for file in disk["files"]:
                if file["name"].startswith("[%s]" % dataStore):
                    return True
    except:
        log.debug('Exception in doesVMDependOnDataStore')
    return False


# check if VMware can snapshot a VM
def canSnapshotVM(vm):
    try:
        # check for PCI pass-through devices
        devs = vm.get_property('devices')
        for dev in devs:
            if devs[dev]['type'] == "VirtualPCIPassthrough":
                return False
        # consider supporting more cases of VMs that can't be snapshoted
        # https://kb.vmware.com/selfservice/microsites/search.do?language=en_US&cmd=displayKC&externalId=1006392
    except:
        log.debug('Exception in canSnapshotVM')
    return True


# check if there is already a snapshot by a given name
def doesVMSnapshotByNameExists(vm, snapshotName):
    try:
        snaps = vm.get_snapshots()
        for snap in snaps:
            if snap.get_name() == snapshotName:
                return True
    except:
        log.debug('Exception in doesVMSnapshotByNameExists')
    return False


appPool.hook_tool_run('autosnap')

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
taskpath = {'recursive': [], 'nonrecursive': []}
for task in TaskObjects:
    if isMatchingTime(task, snaptime):
        if task.task_recursive:
            taskpath['recursive'].append(task.task_filesystem)
        else:
            taskpath['nonrecursive'].append(task.task_filesystem)
        fs = task.task_filesystem
        expire_time = ('%s%s' % (task.task_ret_count, task.task_ret_unit[0])).__str__()
        tasklist = []
        if (fs, expire_time) in mp_to_task_map:
            tasklist = mp_to_task_map[(fs, expire_time)]
            tasklist.append(task)
        else:
            tasklist = [task]
        mp_to_task_map[(fs, expire_time)] = tasklist

re_path = re.compile("^((" + '|'.join(taskpath['nonrecursive']) +
                     ")@|(" + '|'.join(taskpath['recursive']) + ")[@/])")
# Only proceed further if we are  going to generate any snapshots for this run
if len(mp_to_task_map) > 0:

    # Grab all existing snapshot and filter out the expiring ones
    snapshots = {}
    snapshots_pending_delete = set()
    previous_prefix = '/'
    zfsproc = pipeopen("/sbin/zfs list -t snapshot -H -o name", debug, logger=log)
    lines = zfsproc.communicate()[0].split('\n')
    reg_autosnap = re.compile('^auto-(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2}).'
                              '(?P<hour>\d{2})(?P<minute>\d{2})-(?P<retcount>\d+)'
                              '(?P<retunit>[hdwmy])$')
    for snapshot_name in lines:
        if snapshot_name != '':
            fs, snapname = snapshot_name.split('@')
            snapname_match = reg_autosnap.match(snapname)
            if snapname_match is not None:
                snap_infodict = snapname_match.groupdict()
                snap_ret_policy = '%s%s' % (snap_infodict['retcount'], snap_infodict['retunit'])
                if snap_expired(snap_infodict, snaptime):
                    # Only delete the snapshot if there's a snapshot task enabled that created it.
                    if re_path:
                        if re_path.match(snapshot_name):
                            # Destroy of expired snapshots is recursive, so only request so on the
                            # toplevel.
                            if fs.startswith(previous_prefix):
                                if ('%s@%s' % (previous_prefix[:-1], snapname)) in snapshots_pending_delete:
                                    continue
                            else:
                                previous_prefix = '%s/' % (fs)
                            snapshots_pending_delete.add(snapshot_name)
                else:
                    if (fs, snap_ret_policy) in mp_to_task_map:
                        if (fs, snap_ret_policy) in snapshots:
                            last_snapinfo = snapshots[(fs, snap_ret_policy)]
                            if snapinfodict2datetime(last_snapinfo) < snapinfodict2datetime(snap_infodict):
                                snapshots[(fs, snap_ret_policy)] = snap_infodict
                        else:
                            snapshots[(fs, snap_ret_policy)] = snap_infodict

    list_mp = mp_to_task_map.keys()

    for mpkey in list_mp:
        tasklist = mp_to_task_map[mpkey]
        if mpkey in snapshots:
            snapshot_time = snapinfodict2datetime(snapshots[mpkey])
            for taskindex in range(len(tasklist) - 1, -1, -1):
                task = tasklist[taskindex]
                if snapshot_time + timedelta(minutes=task.task_interval) > snaptime:
                    del tasklist[taskindex]
            if len(tasklist) == 0:
                del mp_to_task_map[mpkey]

    snaptime_str = snaptime.strftime('%Y%m%d.%H%M')

    for mpkey, tasklist in mp_to_task_map.items():
        fs, expire = mpkey
        recursive = False
        for task in tasklist:
            if task.task_recursive is True:
                recursive = True
        if recursive is True:
            rflag = ' -r'
        else:
            rflag = ''

        snapname = '%s@auto-%s-%s' % (fs, snaptime_str, expire)

        # If there's a VMWare Plugin object for this filesystem
        # snapshot the VMs before taking the ZFS snapshot.
        # Once we've taken the ZFS snapshot we're going to log back in
        # to VMWare and destroy all the VMWare snapshots we created.
        # We do this because having VMWare snapshots in existance impacts
        # the performance of your VMs.
        qs = VMWarePlugin.objects.filter(filesystem=fs)
        if qs:
            server = VIServer()

            # Generate a unique snapshot name that (hopefully) won't collide with anything
            # that exists on the VMWare side.
            vmsnapname = str(uuid.uuid4())

            # Generate a helpful description that is visible on the VMWare side.  Since we
            # are going to be creating VMWare snaps, if one gets left dangling this will
            # help determine where it came from.
            vmsnapdescription = str(datetime.now()).split('.')[0] + " FreeNAS Created Snapshot"

            # Data structures that will be used to keep track of VMs that are snapped,
            # as wel as VMs we tried to snap and failed, and VMs we realized we couldn't
            # snapshot.
            snapvms = {}
            snapvmfails = {}
            snapvmskips = {}

        # We keep track of snapshots per VMWare "task" because we are going to iterate
        # over all the VMWare tasks for a given ZFS filesystem, do all the VMWare snapshotting
        # then take the ZFS snapshot, then iterate again over all the VMWare "tasks" and undo
        # all the snaps we created in the first place.
        for vmsnapobj in qs:
            snapvms[vmsnapobj] = []
            snapvmfails[vmsnapobj] = []
            snapvmskips[vmsnapobj] = []
            try:
                server.connect(vmsnapobj.hostname,
                               vmsnapobj.username,
                               vmsnapobj.get_password())
            except:
                log.warn("VMware login failed to %s", vmsnapobj.hostname)
                # TODO: This should generate an alert.
                continue
            # There's no point to even consider VMs that are paused or powered off.
            vmlist = server.get_registered_vms(status='poweredOn')
            for vm in vmlist:
                vmobj = server.get_vm_by_path(vm)
                if doesVMDependOnDataStore(vmobj, vmsnapobj.datastore):
                    try:
                        if canSnapshotVM(vmobj):
                            if not doesVMSnapshotByNameExists(vmobj, vmsnapname):
                                # have we already created a snapshot of the VM for this volume
                                # iteration? can happen if the VM uses two datasets (a and b)
                                # where both datasets are mapped to the same ZFS volume in FreeNAS.
                                vmobj.create_snapshot(vmsnapname,
                                                      description=vmsnapdescription,
                                                      memory=False)
                            else:
                                log.debug("Not creating snapshot %s for VM %s because it "
                                          "already exists", vmsnapname, vm)
                        else:
                            # TODO:
                            # we can try to shutdown the VM, if the user provided us an ok to do
                            # so (might need a new list property in obj to know which VMs are
                            # fine to shutdown and a UI to specify such exceptions)
                            # otherwise can skip VM snap and then make a crash-consistent zfs
                            # snapshot for this VM
                            log.log(logging.NOTICE, "Can't snapshot VM %s that depends on "
                                    "datastore %s and filesystem %s."
                                    " Possibly using PT devices. Skipping.",
                                    vm, vmsnapobj.datastore, fs)
                            snapvmskips[vmsnapobj].append(vmobj)
                    except:
                        log.warn("Snapshot of VM %s failed", vm)
                        snapvmfails[vmsnapobj].append(vmobj)
                    snapvms[vmsnapobj].append(vmobj)
            if server.is_connected():
                server.disconnect()
        # At this point we've completed snapshotting VMs.

        # Send out email alerts for VMs we tried to snapshot that failed.
        # Also put the failures into a sentinel file that the alert
        # system can understand.
        for vmsnapobj in qs:
            if snapvmfails[vmsnapobj]:
                try:
                    with LockFile(VMWARE_FAILS) as lock:
                        with open(VMWARE_FAILS, 'rb') as f:
                            fails = pickle.load(f)
                except:
                    fails = {}
                # vmitem.get_property('path') is the reverse of server.get_vm_by_path(vm)
                fails[snapname] = [vmitem.get_property('path') for vmitem in snapvmfails[vmsnapobj]]
                with LockFile(VMWARE_FAILS) as lock:
                    with open(VMWARE_FAILS, 'wb') as f:
                        pickle.dump(fails, f)

                send_mail(
                    subject="VMware Snapshot failed! (%s)" % snapname,
                    text="""
Hello,
    The following VM failed to snapshot %s:
%s
""" % (snapname, '    \n'.join(fails[snapname])),
                    channel='snapvmware'
                )

        # At this point we have finished sending alerts out

        # If there were no failures and we successfully took some VMWare snapshots
        # set the ZFS property to show the snapshot has consistent VM snapshots
        # inside it.
        sentinel = True
        for vmsnapobj in qs:
            if not (len(snapvms[vmsnapobj]) > 0 and len(snapvmfails[vmsnapobj]) == 0):
                sentinel = False
        if sentinel:
            vmflag = '-o freenas:vmsynced=Y '
        else:
            vmflag = ''

        # Take the ZFS snapshot
        MNTLOCK.lock()
        snapcmd = '/sbin/zfs snapshot%s %s"%s"' % (rflag, vmflag, snapname)
        proc = pipeopen(snapcmd, logger=log)
        err = proc.communicate()[1]
        MNTLOCK.unlock()

        if proc.returncode != 0:
            log.error("Failed to create snapshot '%s': %s", snapname, err)
            send_mail(
                subject="Snapshot failed! (%s)" % snapname,
                text="""
Hello,
    Snapshot %s failed with the following error: %s""" % (snapname, err),
                interval=datetime.timedelta(hours=1),
                channel='autosnap',
            )

        # Delete all the VMWare snapshots we just took.

        # This can be a list instead of a dict because we really don't care
        # which VMWare task the failed deletion was fron.
        snapdeletefails = []

        for vmsnapobj in qs:
            try:
                server.connect(vmsnapobj.hostname,
                               vmsnapobj.username,
                               vmsnapobj.get_password())
            except:
                # TODO: We need to alert here as this will leave
                # dangling VMWare snapshots.
                log.warn("VMware login failed to %s", vmsnapobj.hostname)
                continue
            # vm is an object, so we'll dereference that object anywhere it's user facing.
            for vm in snapvms[vmsnapobj]:
                if vm not in snapvmfails[vmsnapobj] and vm not in snapvmskips[vmsnapobj]:
                    # The test above is paranoia.  It shouldn't be possible for a vm to
                    # be in more than one of the three dictionaries.
                    try:
                        vm.delete_named_snapshot(vmsnapname)
                    except:
                        log.debug("Exception delete_named_snapshot %s %s",
                                  vm.get_property('path'), vmsnapname)
                        snapdeletefails.append(vm.get_property('path'))

            # Send out email alerts for VMware snapshot deletions that failed.
            # Also put the failures into a sentinel file that the alert
            # system can understand.
            if snapdeletefails:
                try:
                    with LockFile(VMWARESNAPDELETE_FAILS) as lock:
                        with open(VMWARESNAPDELETE_FAILS, 'rb') as f:
                            fails = pickle.load(f)
                except:
                    fails = {}
                fails[snapname] = [vm.get_property('path') for vm in snapdeletefails]
                with LockFile(VMWARESNAPDELETE_FAILS) as lock:
                    with open(VMWARESNAPDELETE_FAILS, 'wb') as f:
                        pickle.dump(fails, f)

                send_mail(
                    subject="VMware Snapshot deletion failed! (%s)" % snapname,
                    text="""
Hello,
    The following VM snapshot(s) failed to delete %s:
%s
""" % (snapname, '    \n'.join(fails[snapname])),
                    channel='snapvmware'
                )
            if server.is_connected():
                server.disconnect()

    MNTLOCK.lock()
    if not autorepl_running():
        for snapshot in snapshots_pending_delete:
            # snapshots with clones will have destruction deferred
            snapcmd = '/sbin/zfs destroy -r -d "%s"' % (snapshot)
            proc = pipeopen(snapcmd, logger=log)
            err = proc.communicate()[1]
            if proc.returncode != 0:
                log.error("Failed to destroy snapshot '%s': %s", snapshot, err)
    else:
        log.debug("Autorepl running, skip destroying snapshots")
    MNTLOCK.unlock()


os.unlink('/var/run/autosnap.pid')

os.execl('/usr/local/bin/python',
         'python',
         '/usr/local/www/freenasUI/tools/autorepl.py')
