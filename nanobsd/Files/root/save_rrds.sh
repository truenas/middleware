#!/bin/sh

# This script manages the two way sync of rrds to persistant storage.
# If the rrd directory doesn't exist in /var it will search for a
# tarball to unpack from persistant storage and populate /var from that
# If the rrd directory does exist it will archive it to persistant
# storage.

PERSIST_FILE="/data/rrd_dir.tar.bz2"

cd /var/db
if [ -d collectd ]
then
	if tar jcf $PERSIST_FILE.$$ collectd
	then
		mv $PERSIST_FILE.$$ $PERSIST_FILE
	else
		rm -f $PERSIST_FILE.$$
	fi
fi
