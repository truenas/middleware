#!/bin/sh
# Script to check for jail updates
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

if [ ! -d "${JDIR}/${IP}" -a "${IP}" != "all" ]
then
  echo "ERROR: No jail located at $JDIR/$IP"
  exit 5
fi


# End of error checking, now start update checking
#####################################################################

# Check for updates
if [ "$IP" = "all" ] ; then
  cd ${JDIR}
  for i in `ls -d .*.meta`
  do
    if [ ! -e "${i}/ip" ] ; then continue ; fi
    IP="`cat ${i}/ip`"
    set_warden_metadir
    if [ -e "${JMETADIR}/jail-linux" ] ; then continue; fi

    echo "Checking for jail updates to ${IP}"
    echo "################################################"
 
    # Check for meta-pkg updates
    pc-metapkgmanager --chroot ${JDIR}/${IP} checkup

    # Check for system-updates
    chroot ${JDIR}/${IP} cat /usr/sbin/freebsd-update | sed 's|! -t 0|-z '1'|g' | /bin/sh -s 'fetch'
  done
else
  set_warden_metadir
  
  if [ -e "${JMETADIR}/jail-linux" ] ; then
    echo "ERROR: Cannot check for updates to Linux Jails.. Please use any included Linux utilities for your disto."
    exit 5
  fi

   echo "Checking for jail updates to ${IP}..."
   echo "################################################"
   # Check for meta-pkg updates
   pc-metapkgmanager --chroot ${JDIR}/${IP} checkup

   # Check for system-updates
   chroot ${JDIR}/${IP} cat /usr/sbin/freebsd-update | sed 's|! -t 0|-z '1'|g' | /bin/sh -s 'fetch'
fi
