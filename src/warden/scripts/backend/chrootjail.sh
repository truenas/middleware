#!/bin/sh
# Chroot into a working jail
# IP = $1
######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

IP="$1"

if [ -z "${IP}" ]
then
  echo "ERROR: No jail specified to chroot into!"
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

set_warden_metadir

# Make sure the jail is running
jls | grep ${JDIR}/${IP}$ >/dev/null 2>/dev/null
if [ "$?" != "0" ]
then
  echo "ERROR: Jail is not running!"
  exit 6
fi

# Get the JailID for this jail
JID="`jls | grep ${JDIR}/${IP}$ | tr -s " " | cut -d " " -f 2`"

# If on an portjail, make display available
if [ -e "${JMETADIR}/jail-portjail" ] ; then
  HOST="`cat ${JMETADIR}/host`"
  xhost + 2>/dev/null >/dev/null
else
 if [ "`whoami`" != "root" ] ; then
   echo "Error: chroot can only be run as root in standard jails"
   exit 1
 fi
fi

# Done with error checking, now lets chroot into the jail
###################################################################

if [ -z "$2" ] ; then
  echo "Started shell session on ${IP}. Type exit when finished."
  if [ -e "${JMETADIR}/jail-linux" ] ; then
    jailme ${JID} /bin/bash
  else
    jailme ${JID} /bin/csh
  fi
  exit $?
else
  jailme ${JID} ${2}
  exit $?
fi
