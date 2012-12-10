#!/bin/sh
# Install a package set into a jail
######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

IP="$1"

if [ -z "${IP}" ]
then
  echo "ERROR: No jail specified to view packages in!"
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


# Done with error checking, now lets get a package listing
###################################################################
chroot "${JDIR}/${IP}" pkg_info
