#!/bin/sh
# Starts up the warden service
######################################################################

PATH="${PATH}:/usr/local/bin:/usr/local/sbin"
export PATH

# Source our functions
PROGDIR="/usr/local/share/warden"

if [ -z "${PROGDIR}" ]
then
   echo "PROGDIR unset! Is The Warden installed properly?"
   exit 155
fi

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

echo "Stopping the Warden"

# If no jails we can exit
if [ ! -d "${JDIR}" ] ; then exit 0 ; fi

cd ${JDIR}
for i in `ls -d .*.meta 2>/dev/null`
do
  if [ ! -e "${i}/ip" ] ; then continue; fi
  jIP="`cat ${i}/ip`"

  ${PROGDIR}/scripts/backend/checkstatus.sh "${jIP}" 2>/dev/null
  if [ "$?" = "0" ] ; then
    echo "Stopping jail (${jIP})"
    warden stop "${jIP}" "FAST"
  fi
done

