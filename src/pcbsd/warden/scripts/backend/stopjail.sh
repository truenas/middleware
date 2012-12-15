#!/bin/sh
# Script to stop a jail
# Args $1 = jail-dir
#######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

IP="${1}"
if [ "${2}" = "FAST" ]
then
  FAST="Y"
fi

if [ -z "${IP}" ]
then
  echo "ERROR: No jail specified to delete!"
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


HOST="`cat ${JMETADIR}/host`"

# End of error checking, now shutdown this jail
##################################################################

echo -e "Stopping the jail...\c"

# Get the JailID for this jail
JID="`jls | grep ${JDIR}/${IP}$ | tr -s " " | cut -d " " -f 2`"

echo -e ".\c"

# Check if we need umount x mnts
if [ -e "${JMETADIR}/jail-portjail" ] ; then umountjailxfs ${IP} ; fi

# Get list of IPs for this jail
IPS="${IP}"
if [ -e "${JMETADIR}/ip-extra" ] ; then
  while read line
  do
    IPS="${IPS} $line"
  done < ${JMETADIR}/ip-extra
fi

# Check if we need to remove the IP aliases from this jail
for _ip in $IPS
do 
  # See if active alias
  ifconfig $NIC | grep -q "${_ip}"
  if [ $? -ne 0 ] ; then continue ; fi

  isV6 "${_ip}"
  if [ $? -eq 0 ] ; then
    ifconfig $NIC inet6 ${_ip} delete
  else
    ifconfig $NIC inet -alias ${_ip}
  fi
  echo -e ".\c"
done

if [ -e "${JMETADIR}/jail-linux" ] ; then LINUXJAIL="YES" ; fi

if [ "$LINUXJAIL" = "YES" ] ; then
  # If we have a custom stop script
  if [ -e "${JMETADIR}/jail-stop" ] ; then
    sCmd=`cat ${JMETADIR}/jail-stop`
    echo "Stopping jail with: ${sCmd}"
    if [ -n "${JID}" ] ; then
      jexec ${JID} ${sCmd} 2>&1
    fi
  else
    # Check for different init styles
    if [ -e "${JDIR}/${IP}/etc/init.d/rc" ] ; then
      if [ -n "${JID}" ] ; then
        jexec ${JID} /bin/sh /etc/init.d/rc 0 2>&1
      fi
    elif [ -e "${JDIR}/${IP}/etc/rc" ] ; then
      if [ -n "${JID}" ] ; then
        jexec ${JID} /bin/sh /etc/rc 0 2>&1
      fi
    fi
  fi
  sleep 3

  umount -f ${JDIR}/${IP}/sys 2>/dev/null
  umount -f ${JDIR}/${IP}/dev/fd 2>/dev/null
  umount -f ${JDIR}/${IP}/dev 2>/dev/null
  umount -f ${JDIR}/${IP}/lib/init/rw 2>/dev/null
else
  # If we have a custom stop script
  if [ -e "${JMETADIR}/jail-stop" ] ; then
    if [ -n "${JID}" ] ; then
      sCmd=`cat ${JMETADIR}/jail-stop`
      echo "Stopping jail with: ${sCmd}"
      jexec ${JID} ${sCmd} 2>&1
    fi
  else
    if [ -n "${JID}" ] ; then
      echo "Stopping jail with: /etc/rc.shutdown"
      jexec ${JID} /bin/sh /etc/rc.shutdown >/dev/null 2>/dev/null
    fi
  fi
fi

umount -f ${JDIR}/${IP}/dev >/dev/null 2>/dev/null

echo -e ".\c"

# Skip the time consuming portion if we are shutting down
if [ "$FAST" != "Y" ]
then

# We asked nicely, so now kill the jail for sure
killall -j ${JID} -TERM 2>/dev/null
sleep 1
killall -j ${JID} -KILL 2>/dev/null

echo -e ".\c"

# Check if we need to unmount the devfs in jail
mount | grep "${JDIR}/${IP}/dev" >/dev/null 2>/dev/null
if [ "$?" = "0" ]
then
  # Setup a 60 second timer to try and umount devfs, since takes a bit
  SEC="0"
  while
   i=1
  do
   sleep 2

   # Try to unmount dev
   umount -f "${JDIR}/${IP}/dev" 2>/dev/null
   if [ "$?" = "0" ]
   then
      break
   fi

   SEC="`expr $SEC + 2`"
   echo -e ".\c"

   if [ ${SEC} -gt 60 ]
   then
      break
   fi

  done
fi

# Check if we need to unmount any extra dirs
mount | grep "${JDIR}/${IP}/proc" >/dev/null 2>/dev/null
if [ "$?" = "0" ]; then
  umount -f "${JDIR}/${IP}/proc"
fi

if [ -e "${JMETADIR}/jail-portjail" ] ; then
  umountjailxfs
fi

fi # End of FAST check

echo -e ".\c"

if [ -n "${JID}" ] ; then
  jail -r ${JID}
fi

echo -e "Done"


