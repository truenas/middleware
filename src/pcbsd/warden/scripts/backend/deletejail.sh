#!/bin/sh
# Script to stop a jail
# Args $1 = jail-dir
#######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

JAILNAME="$1"
export JAILNAME

if [ -z "${JAILNAME}" ]
then
  warden_error "No jail specified to delete!"
  rtn
  exit 5
fi

if [ -z "${JDIR}" ]
then
  warden_error "JDIR is unset!!!!"
  rtn
  exit 5
fi

JAILDIR="${JDIR}/${JAILNAME}"

if [ ! -d "${JAILDIR}" ] ; then
   warden_error "No such jail at ${JAILDIR}"
   exit 5
fi

set_warden_metadir

# pre-delete hooks
if [ -x "${JMETADIR}/jail-pre-delete" ] ; then
  "${JMETADIR}/jail-pre-delete"
fi

# Check if the jail is running first
${PROGDIR}/scripts/backend/checkstatus.sh "${JAILNAME}" "mount_check"
if [ "$?" = "0" ]
then
  # Make sure the jail is stopped
  ${PROGDIR}/scripts/backend/stopjail.sh "${JAILNAME}"
fi

# Confirm jail was shutdown and no mounts are left
${PROGDIR}/scripts/backend/checkstatus.sh "${JAILNAME}" "mount_check"
if [ "$?" = "0" ] ; then
   warden_error "Jail is still running, or has active mount-points.. Please stop manually."
   exit 5
fi

echo -e "Deleting Jail...\c"
isDirZFS "${JAILDIR}" "1"
if [ $? -eq 0 ] ; then
  # Create ZFS mount
  tank="`getZFSTank "$JDIR"`"
  jailp="`getZFSRelativePath "${JAILDIR}"`"
  zfs destroy -fr "${tank}${jailp}"
  rmdir "${JAILDIR}" 2>/dev/null
else
  chflags -R noschg "${JAILDIR}"
  rm -rf "${JAILDIR}"
fi

if [ ! -z "${JMETADIR}" -a "${JMETADIR}" != " " ] ; then
  rm -rf "${JMETADIR}"
fi

# post-delete hooks
if [ -x "${JMETADIR}/jail-post-delete" ] ; then
  "${JMETADIR}/jail-post-delete"
fi

warden_print "Done"
