#!/bin/sh
# Script to check a jail status
# Args $1 = JAILNAME
######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

JAILNAME="$1"

if [ -z "${JAILNAME}" ]
then
  echo "ERROR: You must specify a jail to check"
  exit 5
fi

if [ -z "${JDIR}" ]
then
  echo "ERROR: JDIR is unset!!!!"
  exit 5
fi

JAILDIR="${JDIR}/${JAILNAME}"

if [ ! -d "${JAILDIR}" ]
then
  echo "ERROR: No jail located at ${JAILDIR}"
  exit 5
fi

set_warden_metadir

IP="`cat ${JMETADIR}/ip`"

# Display details about this jail now
#####################################################################
echo "Details for jail: ${JAILNAME}"
isDirZFS "${JAILDIR}" "1"
if [ $? -eq 0 ] ; then 
   tank=`getZFSTank "${JAILDIR}"`
   diskUsage=`df -m | grep -w ${tank}${JAILDIR}$ | awk '{print $3}'`
else
   diskUsage=`du -c -x -m ${JAILDIR} 2>/dev/null | grep total | tail -n 1 | awk '{print $1}'`
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
