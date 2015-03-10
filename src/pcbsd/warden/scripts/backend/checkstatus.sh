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
for mountpoint in $(mount | grep -e "${JAILDIR}/" | cut -d" " -f3); do
  hasmount="1"
done

# A jail with spaces in the name? quote it
JAILNAME2="$(echo "${JAILNAME}"|awk '{ print $1 }')"
if [ "${JAILNAME}" != "${JAILNAME2}" ]
then
    JAILNAME="\"${JAILNAME}\""
fi

# Check if a jail with the same name is running AND if the jail is active
JAIL="`jls name|awk -v jail="^${JAILNAME}\$" '$0 ~ jail { print $0 }'`" # for running
JID="`jls | grep "${JAILDIR}"$ | tr -s " " | cut -d " " -f 2`" # for active with the correct dataset
if [ -n "${JID}" -a -n "${JAIL}" ]; then
  exit 0
else
    if [ "$2" = "mount_check" -a "$hasmount" = "1" ]; then
	exit 0
    fi
  exit 1
fi
