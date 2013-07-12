#!/bin/sh
# Script to create a directory, and if on ZFS create a new dataset for it

# Source our functions
. /usr/local/share/pcbsd/scripts/functions.sh

dir="$1"

if [ -d "$dir" ] ; then
   exit_err "Directory $dir already exists!"
fi

# Is this on ZFS?
isDirZFS "${dir}"
if [ $? -eq 0 ] ; then
  # Create ZFS mount
  tank=`getZFSTank "$dir"`
  zfs create -o mountpoint=${dir} -p ${tank}${dir}
else
  mkdir -p "${dir}"
fi
