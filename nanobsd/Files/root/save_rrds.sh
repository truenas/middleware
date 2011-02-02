#!/bin/sh

# This script manages the two way sync of rrds to persistant storage.
# If the rrd directory doesn't exist in /var it will search for a
# tarball to unpack from persistant storage and populate /var from that
# If the rrd directory does exist it will archive it to persistant
# storage.

PERSIST_FILE="/data/rrd_dir.tar.bz2"


if [ -d /var/db/collectd ]; then
    (cd /var/db && tar jcf ${PERSIST_FILE} collectd)
fi
