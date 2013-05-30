#!/bin/sh
# Script to setup the initial rootpw on a jail
# Args $1 = JAILDIR
# Args $2 = rootPW
######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

JAILNAME="$1"
ROOTPW="${2}"

export ROOTPW

if [ -z "${JAILNAME}" ]
then
  warden_error "You must specify a jail"
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

if [ -z "${ROOTPW}" ]
then
  warden_error "Missing root pw!"
  exit 5
fi

set_warden_metadir


# End of error checking, now lets add the users / passwords
#####################################################################

warden_printf "Changing root password on: ${IP} "

if [ -e "${JMETADIR}/jail-linux" ] ; then

  echo '#!/bin/bash
echo -e "${ROOTPW}\n${ROOTPW}" | passwd root
' > "${JAILDIR}/.chpass.sh"

else

  echo '#!/bin/sh
echo "${ROOTPW}" | pw usermod root -h 0
' > "${JAILDIR}/.chpass.sh"

fi

chmod 755 "${JAILDIR}/.chpass.sh"
chroot "${JAILDIR}" /.chpass.sh
if [ $? -eq 0 ] ; then
  warden_print "Success!"
else
  warden_error "FAILED!"
fi

rm "${JAILDIR}/.chpass.sh"


unset ROOTPW
