#!/bin/sh
# Script to stop a jail
# Args $1 = jail-dir
#######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

IP="$1"

if [ -z "${IP}" ]
then
  echo "ERROR: No jail specified to delete!"
  rtn
  exit 5
fi

if [ -z "${JDIR}" ]
then
  echo "ERROR: JDIR is unset!!!!"
  rtn
  exit 5
fi

if [ ! -d "${JDIR}/${IP}" ] ; then
   echo "ERROR: No such jail at ${JDIR}/${IP}"
   exit 5
fi

set_warden_metadir

# Check if the jail is running first
${PROGDIR}/scripts/backend/checkstatus.sh "${IP}"
if [ "$?" = "0" ]
then
  # Make sure the jail is stopped
  ${PROGDIR}/scripts/backend/stopjail.sh "${IP}"
fi

# Confirm jail was shutdown and no mounts are left
${PROGDIR}/scripts/backend/checkstatus.sh "${IP}"
if [ "$?" = "0" ] ; then
   echo "ERROR: Jail is still running, or has active mount-points.. Please stop manually."
   exit 5
fi

echo -e "Deleting Jail...\c"
isDirZFS "${JDIR}/${IP}" "1"
if [ $? -eq 0 ] ; then
  # Create ZFS mount
  tank=`getZFSTank "$JDIR"`
  zfs destroy -r ${tank}${JDIR}/${IP}
  rmdir ${JDIR}/${IP} 2>/dev/null
else
  chflags -R noschg "${JDIR}/${IP}"
  rm -rf "${JDIR}/${IP}"
fi

if [ ! -z "${JMETADIR}" -a "${JMETADIR}" != " " ] ; then
  rm -rf "${JMETADIR}"
fi

echo "Done"

