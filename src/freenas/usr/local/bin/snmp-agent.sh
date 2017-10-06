#!/bin/sh
while true
do
	/usr/local/bin/python /usr/local/bin/snmp-agent.py &
	PID=$!
	echo $PID > /var/run/snmp-agent.pid
	wait $PID
	if [ $? -ne 1 ]
	then
		break
	fi
done
