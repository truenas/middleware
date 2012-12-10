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

# End of error checking, now see if the jail is active
#####################################################################

# Check if anything is still mounted in this jail
hasmount="0"
for mountpoint in $(mount | grep -e '${JDIR}/${IP}/' | cut -d" " -f3); do
  hasmount="1"
done

# Check if the jail is active
jls | grep ${JDIR}/${IP}$ >/dev/null 2>/dev/null
if [ "$?" = "0" -o "$hasmount" = "1" ]; then
  exit 0
else
  exit 1
fi



