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
CLONE="${2}"

if [ -z "${CLONE}" ] ; then
   warden_error "No clone specified!"
   exit 1
fi

if [ -z "${JAILNAME}" ]
then
  warden_error "No jail specified to start!"
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

rmZFSClone "${JAILDIR}" "${CLONE}" "${JAILNAME}"
