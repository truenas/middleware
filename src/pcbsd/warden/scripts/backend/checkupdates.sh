#!/bin/sh
# Script to check for jail updates
# Args $1 = JAILNAME
######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

JAILNAME="$1"

if [ -z "${JAILNAME}" ]
then
  warden_error "You must specify a jail to check"
  exit 5
fi

if [ -z "${JDIR}" ]
then
  warden_error "JDIR is unset!!!!"
  exit 5
fi

JAILDIR="${JDIR}/${JAILNAME}"

if [ ! -d "${JAILDIR}" -a "${JAILNAME}" != "all" ]
then
  warden_error "No jail located at ${JAILDIR}"
  exit 5
fi


# End of error checking, now start update checking
#####################################################################

# Check for updates
if [ "${JAILNAME}" = "all" ] ; then
  cd ${JDIR}
  for i in `ls -d .*.meta`
  do
    JAILNAME=`echo ${i}|sed 's|.meta$||'|sed 's|^.||'`
    HOST="`cat ${i}/host`"
    set_warden_metadir
    if [ -e "${JMETADIR}/jail-linux" ] ; then continue; fi

    warden_print "Checking for jail updates to ${HOST}"
    warden_print "################################################"

    # Check for pkgng updates
    if [ -e "${JDIR}/${JAILNAME}/usr/local/sbin/pkg-static" ] ; then
       chroot "${JDIR}/${JAILNAME}" pkg upgrade -n
    fi

    # Check for system-updates
    chroot ${JDIR}/${JAILNAME} cat /usr/sbin/freebsd-update | sed 's|! -t 0|-z '1'|g' | /bin/sh -s 'fetch'
  done
else
  set_warden_metadir
  
  if [ -e "${JMETADIR}/jail-linux" ] ; then
    warden_error "Cannot check for updates to Linux Jails.. Please use any included Linux utilities for your disto."
    exit 5
  fi

   warden_print "Checking for jail updates to ${JAILNAME}..."
   warden_print "################################################"

   # Check for pkgng updates
   if [ -e "${JDIR}/${JAILNAME}/usr/local/sbin/pkg-static" ] ; then
      chroot "${JDIR}/${JAILNAME}" pkg upgrade -n
   fi

   # Check for system-updates
   chroot ${JDIR}/${JAILNAME} cat /usr/sbin/freebsd-update | sed 's|!  -t 0|-z '1'|g' | /bin/sh -s 'fetch'
fi
