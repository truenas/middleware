#!/bin/sh
# ZFS functionality
# Args $1 = jail-name
# Args $2 = zfs directive
#######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

JAILNAME="${1}"
ACTION="${2}"

if [ -z "${JAILNAME}" ]
then
  echo "ERROR: No jail specified to start!"
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

if [ "$ACTION" = "start" ] ; then
  isDirZFS "${JAILDIR}" "1"
  if [ $? -ne 0 ] ; then printerror "Not a ZFS volume: ${1}" ; fi

  TIME="${3}"
  COUNT="${4}"
  case $TIME in
  daily|hourly) ;;
	*) echo "ERROR: Invalid frequency specified!" ; exit 5 ;;
  esac
  if [ ! $(is_num "$COUNT") ] ; then
     echo "ERROR: Invalid count specified!" ; exit 5
  fi

  enable_cron
  echo "${TIME}" >${JMETADIR}/cron
  echo "${COUNT}" >${JMETADIR}/cron-keep
  echo "Snapshot frequency set: $TIME"
  echo "Snapshot days to keep set: $COUNT"
  exit 0
fi

if [ "$ACTION" = "stop" ] ; then
   rm ${JMETADIR}/cron 2>/dev/null >/dev/null
   rm ${JMETADIR}/cron-keep 2>/dev/null >/dev/null
   exit 0
fi

