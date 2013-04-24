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

IP4="`cat ${JMETADIR}/ipv4 2>/dev/null`"
if [ -n "${IP4}" ] ; then
  get_ip_and_netmask "${IP4}"
  IP4="${JIP}"
  MASK4="${JMASK}"
fi

IP6="`cat ${JMETADIR}/ipv6 2>/dev/null`"
if [ -n "${IP6}" ] ; then
  get_ip_and_netmask "${IP6}"
  IP6="${JIP}"
  MASK6="${JMASK}"
fi

# Display details about this jail now
#####################################################################
echo "Details for jail: ${JAILNAME}"
isDirZFS "${JAILDIR}" "1"
if [ $? -eq 0 ] ; then 
   tank=`getZFSDataset "${JAILDIR}"`
   diskUsage=`df -m | grep -w "^${tank} " | awk '{print $3}'`
else
   diskUsage=`du -c -x -m ${JAILDIR} 2>/dev/null | grep total | tail -n 1 | awk '{print $1}'`
fi

portList4=
activeCon4=
if [ -n "${IP4}" ] ; then
   sockstat | grep "${IP4}" | grep '*.*' | awk '{print $6}' | sed "s|${IP4}:||g" | sort -g | uniq >/tmp/.socklist4.$$
   while read line
   do
     if [ -z "$portList4" ] ; then
       portList4="${line}" 
     else
       portList4="${portList4},$line" 
     fi
   done < /tmp/.socklist4.$$
   rm /tmp/.socklist4.$$
   activeCon4=`sockstat | grep "${IP4}" | grep -v '*.*' | wc -l | awk '{print $1}'`
fi

portList6=
activeCon6=
if [ -n "${IP6}" ] ; then
   sockstat | grep "${IP6}" | grep '*.*' | awk '{print $6}' | sed "s|${IP6}:||g" | sort -g | uniq >/tmp/.socklist6.$$
   while read line
   do
     if [ -z "$portList6" ] ; then
       portList6="${line}" 
     else
       portList6="${portList6},$line" 
     fi
   done < /tmp/.socklist6.$$
   rm /tmp/.socklist6.$$
   activeCon6=`sockstat | grep "${IP6}" | grep -v '*.*' | wc -l | awk '{print $1}'`
fi

echo "Disk Usage: ${diskUsage}MB"

echo "Active IPv4 Ports: ${portList4}"
echo "Current IPv4 Connections: ${activeCon4}"

echo "Active IPv6 Ports: ${portList6}"
echo "Current IPv6 Connections: ${activeCon6}"
