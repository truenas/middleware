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

import argparse
import os


def main(no_delete, hold, dataset, skipstate):
    # If no_delete is True, print out snapshots but don't delete the
    # hold on them.
    # hold is the name of the hold to operate on.  The default is freenas:repl, which
    # is the hold that the old replicator used on snapshots
    # dataset is a string that must match the beginning of the snapname
    # It can be used to  "root" the list eg: -d tank/whatever would only
    # operate on snapshots in the tank/whatever dataset or it's descendants
    snaplist = os.popen("zfs list -t snapshot | awk '{print $1}'").readlines()
    snaplist = [x for x in snaplist[1:] if not x.startswith("freenas-boot")]
    if dataset:
        snaplist = [x for x in snaplist if x.startswith(dataset)]
    print("Checking for holds")
    hold_delete = False
    for snap in snaplist:
        ret = os.popen("zfs holds %s" % snap).readlines()
        if len(ret) > 1:
            for item in ret[1:]:
                if item.split()[1] == hold:
                    if no_delete:
                        print("%s hold found on %s" % (hold, snap))
                    else:
                        print("Destroying %s hold on %s" % (hold, snap))
                        ret = os.system("zfs release %s %s" % (item.split()[1], snap))
                        if ret != 0:
                            print("Error releasing hold on %s" % snap)
                        else:
                            hold_delete = True
    if not hold_delete:
        print("No holds found")

    if not skipstate:
        poollist = os.popen("zpool list -H | awk '{print $1}'").readlines()
        for pool in poollist:
            pool = pool.strip()
            if pool != "freenas-boot":
                print("Removing freenas:state on %s" % pool)
                ret = os.system("zfs inherit -r freenas:state %s" % pool)
                if ret != 0:
                    print("Error removing freenas:state on %s" % pool)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="List or remove holds from snapshots")
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
    args = parser.parse_args()
    main(args.n, args.c, args.d, args.s)
