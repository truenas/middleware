#!/bin/sh
if [ -f /data/freenas-v1.db ]; then
	enabled=$(/usr/local/bin/sqlite3 /data/freenas-v1.db "SELECT adv_uploadcrash FROM system_advanced")
	if [ ${enabled} -eq 1 ]; then
		rm -f /var/log/telemetry.json.bz2
		/usr/local/bin/python /usr/local/bin/telemetry-gather.py /var/log/messages*
		tar -C /var/db/collectd/rrd/localhost -jcf /var/db/collectd/rrd/rrds.tar.bz2 . 		
		/usr/local/bin/python /usr/local/bin/telemetryuploader --jitter /var/log/telemetry.json.bz2  /var/db/collectd/rrd/rrds.tar.bz2
		rm -f /var/db/collectd/rrd/rrds.tar.bz2 
	fi
fi

