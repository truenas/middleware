#!/bin/sh
# Chroot into a working jail
# JAILNAME = $1
######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

JAILNAME="$1"

if [ -z "${JAILNAME}" ]
then
  warden_error "No jail specified to chroot into!"
  exit 5
fi

if [ -z "${JDIR}" ]
then
  warden_error "JDIR is unset!!!!"
  exit 5
fi

JAILDIR="${JDIR}/${JAILNAME}"

if [ ! -d "${JAILDIR}" ]
then
  warden_error "No jail located at ${JAILDIR}"
  exit 5
fi

set_warden_metadir

# Make sure the jail is running
jls | grep ${JAILDIR}$ >/dev/null 2>/dev/null
if [ "$?" != "0" ]
then
  warden_error "Jail is not running!"
  exit 6
fi

# Get the JailID for this jail
JID="`jls | grep ${JAILDIR}$ | tr -s " " | cut -d " " -f 2`"

# If on an portjail, make display available
if [ -e "${JMETADIR}/jail-portjail" ] ; then
  HOST="`cat ${JMETADIR}/host`"
  xhost + 2>/dev/null >/dev/null
else
 if [ "`whoami`" != "root" ] ; then
   warden_error "chroot can only be run as root in standard jails"
   exit 1
 fi
fi

# Done with error checking, now lets chroot into the jail
###################################################################

if [ -z "$2" ] ; then
  echo "Started shell session on ${JAILNAME}. Type exit when finished."
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
