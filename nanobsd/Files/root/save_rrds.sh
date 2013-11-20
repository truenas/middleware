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
	if tar jcf ${PERSIST_FILE##*/}.$$ collectd > /dev/null 2>&1
	then
		avail=$(df -k /data | grep /data | awk '{print ($2-$3-20)*1024}')
		if [ -f ${PERSIST_FILE} ]; then
			avail=$((${avail}+$(ls -l ${PERSIST_FILE} | awk '{print $5}')))
		fi
		rrdsize=$(ls -l ${PERSIST_FILE##*/}.$$ | awk '{print $5}')
		if [ ${avail} -le ${rrdsize} ]; then
			logger Not enough space on /data to save collectd data
			touch /var/tmp/.rrd_enospace
		else
			mv ${PERSIST_FILE##*/}.$$ $PERSIST_FILE
		fi
	else
		rm -f ${PERSIST_FILE##*/}.$$
	fi
fi
