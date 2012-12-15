#!/bin/sh
# Script to check a jail status
# Args $1 = IP
######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

IP="$1"

if [ -z "$IP" ]
then
  echo "ERROR: You must specify an IP to check"
  exit 5
fi

if [ -z "${JDIR}" ]
then
  echo "ERROR: JDIR is unset!!!!"
  exit 5
fi

if [ ! -d "${JDIR}/${IP}" ]
then
  echo "ERROR: No jail located at $JDIR/$IP"
  exit 5
fi

# Display details about this jail now
#####################################################################
echo "Details for jail: ${IP}"
isDirZFS "${JDIR}/${IP}" "1"
if [ $? -eq 0 ] ; then 
   tank=`getZFSTank "${JDIR}/${IP}"`
   diskUsage=`df -m | grep -w ${tank}${JDIR}/${IP}$ | awk '{print $3}'`
else
   diskUsage=`du -c -x -m ${JDIR}/${IP} 2>/dev/null | grep total | tail -n 1 | awk '{print $1}'`
fi
sockstat | grep "${IP}" | grep '*.*' | awk '{print $6}' | sed "s|${IP}:||g" | sort -g | uniq >/tmp/.socklist.$$
while read line
do
  if [ -z "$portList" ] ; then
    portList="${line}" 
  else
    portList="${portList},$line" 
  fi
done < /tmp/.socklist.$$
rm /tmp/.socklist.$$
activeCon=`sockstat | grep "${IP}" | grep -v '*.*' | wc -l | awk '{print $1}'`

echo "Disk Usage: ${diskUsage}MB"
echo "Active Ports: ${portList}"
echo "Current Connections: ${activeCon}"
