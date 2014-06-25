#!/bin/sh

# This script manages the two way sync of rrds to persistant storage.
# If the rrd directory doesn't exist in /var it will search for a
# tarball to unpack from persistant storage and populate /var from that
# If the rrd directory does exist it will archive it to persistant
# storage.

. /etc/rc.freenas

PERSIST_FILE="/data/rrd_dir.tar.bz2"

get_system_pool()
{
	${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		sys_pool
	FROM
		system_systemdataset
	ORDER BY
		-id
	LIMIT 1
	" | \
	while read -r system_pool
	do
		echo "${system_pool}"
	done
}

use_rrd_dataset()
{
	local use
	local pool

	if ! is_freenas
	then
		return 1
	fi

	pool="$(get_system_pool)"
	if [ -z "${pool}" ]
	then
		return 1
	fi

	use="$(${FREENAS_SQLITE_CMD} ${FREENAS_CONFIG} "
	SELECT
		sys_rrd_usedataset
	FROM
		system_systemdataset
	ORDER BY
		-id
	LIMIT 1
	" | \
	while read -r rrd_usedataset
	do
		if [ "${rrd_usedataset}" = "0" ]
		then
			echo "1"
		else
			echo "0"
		fi
	done
	)"

	return ${use}
}

if use_rrd_dataset
then
	exit 0
fi

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
			rm -f ${PERSIST_FILE}
			mv ${PERSIST_FILE##*/}.$$ $PERSIST_FILE
		fi
	else
		rm -f ${PERSIST_FILE##*/}.$$
	fi
fi
