#!/bin/sh
# Install a package set into a jail
######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

JAILNAME="$1"

if [ -z "${JAILNAME}" ]
then
  echo "ERROR: No jail specified to view packages in!"
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

# Done with error checking, now lets get a package listing
###################################################################

# Check if we are using pkgng or old-style
if [ -e "${JAILDIR}/usr/local/sbin/pkg-static" ] ; then
  chroot "${JAILDIR}" pkg info
else
  chroot "${JAILDIR}" pkg_info
fi
