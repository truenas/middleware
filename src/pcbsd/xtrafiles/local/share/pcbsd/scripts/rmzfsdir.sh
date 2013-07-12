#!/bin/sh
# Script to remove a directory, and if on ZFS remove the dataset for it

# Source our functions
. /usr/local/share/pcbsd/scripts/functions.sh

dir="$1"

if [ -z "$dir" ] ; then
   exit_err "Missing directory to remove!"
fi

if [ "$dir" = "/" ] ; then
   exit_err "Refusing to remove /"
fi

if [ ! -d "$dir" ] ; then
   exit_err "Directory $dir does not exist!"
fi

# Is this on ZFS?
isDirZFS "${dir}"
if [ $? -eq 0 ]; then
  tank=`getZFSTank "$dir"`
  zfs destroy -r ${tank}${dir}
  rmdir ${dir}
else
  chflags -R noschg "${dir}"
  rm -rf "${dir}"
fi
