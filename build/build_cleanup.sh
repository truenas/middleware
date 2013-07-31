#!/bin/sh

mydir=`dirname $0`
TOP="$mydir/.."

cd "$TOP"
set -x
set -e
if [ -e os-base ] ; then
	chflags -Rv noschg os-base
fi

# clean up devfs mounts
set +e
for mount_dir in os-base/amd64/_.w/dev os-base/amd64/jails/jail-i386/dev ; do
    if [ -e "$mount_dir" ] ; then
    	umount $mount_dir
    fi
done
set -e

if [ -d pbi ] ; then
	zfs destroy -r `realpath pbi | sed 's@^/@@'`
fi
