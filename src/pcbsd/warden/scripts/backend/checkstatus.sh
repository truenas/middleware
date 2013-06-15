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
  warden_error "You must specify a jail name to check"
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

# End of error checking, now see if the jail is active
#####################################################################

# Check if anything is still mounted in this jail
hasmount="0"
for mountpoint in $(mount | grep -e '${JAILDIR}/' | cut -d" " -f3); do
  hasmount="1"
done

# Check if the jail is active
jls | grep -w ${JAILNAME}$ >/dev/null 2>/dev/null
if [ "$?" = "0" -o "$hasmount" = "1" ]; then
  exit 0
else
  exit 1
fi
