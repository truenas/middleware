#!/bin/sh
# Script to setup the initial rootpw on a jail
# Args $1 = IP
# Args $2 = rootPW
######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

IP="$1"
ROOTPW="${2}"

export ROOTPW


if [ -z "$IP" ]
then
  echo "ERROR: You must specify an IP of a jail"
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

if [ -z "${ROOTPW}" ]
then
  echo "ERROR: Missing root pw!"
  exit 5
fi

set_warden_metadir


# End of error checking, now lets add the users / passwords
#####################################################################

echo -e "Changing root password on: ${IP} \c"

if [ -e "${JMETADIR}/jail-linux" ] ; then

  echo '#!/bin/bash
echo -e "${ROOTPW}\n${ROOTPW}" | passwd root
' > "${JDIR}/${IP}/.chpass.sh"

else

  echo '#!/bin/sh
echo "${ROOTPW}" | pw usermod root -h 0
' > "${JDIR}/${IP}/.chpass.sh"

fi

chmod 755 "${JDIR}/${IP}/.chpass.sh"
chroot "${JDIR}/${IP}" /.chpass.sh
if [ $? -eq 0 ] ; then
  echo -e "Success!"
else
  echo -e "FAILED!"
fi

rm "${JDIR}/${IP}/.chpass.sh"


unset ROOTPW
