#!/usr/local/bin/python
# Copyright (c) 2015 iXsystems, Inc.
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

# Destroy holds created by the old FreeNAS snapshot replicator
# on any snapshot other than those of freenas-boot
# By using the -c and -d switches you can operate on arbitrary datasets
# and test for arbitrary hold names
# Also removes freenas:state properties used by the old replicator

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
from freenasUI.common.pipesubr import pipeopen
from freenasUI.common.locks import mntlock
from freenasUI.common.system import send_mail, get_sw_name

import argparse

log = logging.getLogger('tools.replfix')

is_truenas = not (get_sw_name().lower() == 'freenas')

def rcro():
    if is_truenas:
        return '-o readonly=on '
    else:
        return ''

def RemoteFix(testonly = False, debug = False):
    """
    Go through all the replications, and fix them.
    (Currently means set them read-only.)
    """
    for replication in Replication.objects.all():
        remote = replication.repl_remote.ssh_remote_hostname.__str__()
        remote_port = replication.repl_remote.ssh_remote_port
        dedicateduser = replication.repl_remote.ssh_remote_dedicateduser
        cipher = replication.repl_remote.ssh_cipher
        localfs = replication.repl_filesystem.__str__()
        remotefs = replication.repl_zfs.__str__()
        recursive = not not replication.repl_userepl

        if not replication.repl_enabled:
            continue
                    
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

        rzfscmd = "zfs set readonly=on %s" % remotefs_final
        
        log.debug("rzfscmd = %s" % rzfscmd)
        if debug:
            print >> sys.stderr, rzfscmd
            
        if testonly:
            log.debug("%s %s" % (sshcmd, rzfscmd))
        else:
            zfsproc = pipeopen("%s %s" % (sshcmd, rzfscmd))
            output, error = zfsproc.communicate()
            error = error.strip('\n').strip('\r').replace('WARNING: enabled NONE cipher', '')
            if zfsproc.returncode:
                log.debug("Could not set readonly")
        if recursive:
            zfscmd = "zfs list -H -o name -r " + localfs
            zfsproc = pipeopen(zfscmd)
            output, error = zfsproc.communicate()
            if zfsproc.returncode:
                log.debug("Could not get children of local dataset %s" % localfs)
            else:
                datasets = sorted(output.rstrip().split('\n'))
                for ds in datasets[1:]:
                    # We only want the children
                    remote_dataset = "%s%s" % (ds.partition('/')[1], ds.partition('/')[2])
                    rzfscmd = "zfs inherit readonly %s%s" % (remotefs, remote_dataset)
                    if debug:
                        print >> sys.stderr, "rzfscmd = %s" % rzfscmd
                    log.debug("%s %s" % (sshcmd, rzfscmd))
                    if not testonly:
                        rzfsproc = pipeopen("%s %s" % (sshcmd, rzfscmd))
                        output, error = rzfsproc.communicate()
                        error = error.strip('\n').strip('\r').replace('WARNING: enabled NONE cipher', '')
                        if rzfsproc.returncode:
                            log.debug("Could not inherit readonly on remote %s%s: %s" % (
                                    remotefs,
                                    remote_dataset,
                                    error))
    return

def main(no_delete, hold, dataset, skipstate, remote=False, debug=False, testonly=False):
    # If no_delete is True, print out snapshots but don't delete the
    # hold on them.
    # hold is the name of the hold to operate on.  The default is freenas:repl, which
    # is the hold that the old replicator used on snapshots
    # dataset is a string that must match the beginning of the snapname
    # It can be used to  "root" the list eg: -d tank/whatever would only
    # operate on snapshots in the tank/whatever dataset or it's descendants

    zfscmd = "zfs list -H -t snapshot -o name"
    if dataset:
        zfscmd = zfscmd + "-r %s" % dataset
    snaplist = os.popen("zfs list -H -t snapshot -o name").readlines()
    snaplist = [x for x in snaplist if not x.startswith("freenas-boot")]
                        
    print "Checking for holds"
    hold_delete = False
    for snap in snaplist:
        ret = os.popen("zfs holds %s" % snap).readlines()
        if len(ret) > 1:
            for item in ret[1:]:
                if item.split()[1] == hold:
                    if no_delete or testonly:
                        print "%s hold found on %s" % (hold, snap)
                    else:
                        print "Destroying %s hold on %s" % (hold, snap)
                        zfscmd = "zfs release %s %s" % (item.split()[1], snap)
                        if debug:
                            print zfscmd
                        ret = os.system(zfscmd)
                        if ret != 0:
                            print "Error releasing hold on %s" % snap
                        else:
                            hold_delete = True
    if not hold_delete:
        print "No holds found"

    if not skipstate:
        poollist = os.popen("zpool list -H -o name").readlines()
        for pool in poollist:
            pool = pool.strip()
            if pool != "freenas-boot":
                print "Removing freenas:state on %s" % pool
                zfscmd = "zfs inherit -r freenas:state %s" % pool
                if debug or testonly:
                    print zfscmd
                if not testonly:
                    ret = os.system(zfscmd)
                    if ret != 0:
                        print "Error removing freenas:state on %s" % pool

    if remote:
        RemoteFix(testonly = testonly, debug = debug)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List or remove holds from snapshots")
    parser.add_argument("-D",
                        help="Turn on debugging",
                        action="store_true",
                        default=False)
    parser.add_argument("-N",
                        help="Test only, do not perform any actions",
                        action="store_true",
                        default=False)
    parser.add_argument("-n",
                        help="Print a list of snapshots that have holds "
                             "but don't remove the holds",
                        action="store_true")
    parser.add_argument("-c",
                        help="ZFS hold name to operate on (defaults to freenas:repl)",
                        default="freenas:repl")
    parser.add_argument("-d",
                        help="ZFS dataset name to root the snapshot list to (If not specified "
                             "all ZFS pools and datasets are searched except for freenas-boot)",
                        default=None)
    parser.add_argument("-s",
                        help="Skip cleaning up freenas:state properties left by the old "
                             "replication system.",
                        action="store_true")
    parser.add_argument("-r",
                        help="Set remote datasets to readonly (defaults to true)",
                        action="store_true",
                        default=True)
    args = parser.parse_args()
    main(args.n, args.c, args.d, args.s, remote=args.r, debug=args.D, testonly=args.N)
