#!/bin/sh 
# Script to stop a jail
# Args $1 = jail-name
#######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

JAILNAME="${1}"
export JAILNAME

if [ "${2}" = "FAST" ]
then
  FAST="Y"
fi

if [ -z "${JAILNAME}" ]
then
  warden_error "No jail specified to delete!"
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

# pre-stop hooks
if [ -x "${JMETADIR}/jail-pre-stop" ] ; then
  "${JMETADIR}/jail-pre-stop"
fi

HOST="`cat "${JMETADIR}/host"`"

# Check if we need to enable vnet
VIMAGEENABLE="NO"
if [ -e "${JMETADIR}/vnet" ] ; then
  VIMAGEENABLE="YES"
fi

IFACE=
DEFAULT=0

# Make sure jail uses special interface if specified
if [ -e "${JMETADIR}/iface" ] ; then
  IFACE="`cat "${JMETADIR}/iface"`"
fi
if [ -z "${IFACE}" ] ; then
   IFACE="`get_default_interface`"
   DEFAULT=1
fi

# End of error checking, now shutdown this jail
##################################################################

warden_printf "%s" "Stopping the jail..."

# Get the JailID for this jail
JID="`jls | grep "${JAILDIR}"$ | tr -s " " | cut -d " " -f 2`"

warden_printf "%s" "."

if [ "$VIMAGEENABLE" = "YES" ] ; then
  jail_interfaces_down "${JID}"

else
  # Get list of IP4s for this jail
  IP4S="$(warden_get_ipv4 '' 1)"
  IP4S="${IP4S} $(warden_get_ipv4_aliases '' 1)"

  # Get list of IP6s for this jail
  IP6S="$(warden_get_ipv6 '' 1)"
  IP6S="${IP6S} $(warden_get_ipv6_aliases '' 1)"

  # Check if we need to remove the IP aliases from this jail
  for _ip in $IP4S
  do
    # See if active alias
    if [ -n "${IFACE}" ]
    then
      ifconfig "$IFACE" | grep -q "${_ip}"
      if [ $? -ne 0 ] ; then continue ; fi

      ifconfig "$IFACE" inet -alias "${_ip}"
    fi
  done

  for _ip in $IP6S
  do
    # See if active alias
    if [ -n "${IFACE}" ]
    then
      ifconfig "$IFACE" | grep -q "${_ip}"
      if [ $? -ne 0 ] ; then continue ; fi

      ifconfig "$IFACE" inet6 "${_ip}" delete
    fi
  done
fi


if [ -e "${JMETADIR}/jail-linux" ] ; then LINUXJAIL="YES" ; fi

# Check for user-supplied mounts
if [ -s "${JMETADIR}/fstab" ] ; then
   warden_print "Unmounting user-supplied file-systems"
   cat "${JMETADIR}/fstab" \
     | sed "s|%%JAILDIR%%|${JAILDIR}|g" \
     | sort -r -k 2 > /tmp/.wardenfstab.$$
   umount -a -F /tmp/.wardenfstab.$$
   rm /tmp/.wardenfstab.$$
fi

if [ "$LINUXJAIL" = "YES" ] ; then
  # If we have a custom stop script
  if [ -e "${JMETADIR}/jail-stop" ] ; then
    sCmd=`cat "${JMETADIR}/jail-stop"`
    warden_print "Stopping jail with: ${sCmd}"
    if [ -n "${JID}" ] ; then
      jexec ${JID} ${sCmd} 2>&1
    fi
  else
    # Check for different init styles
    if [ -e "${JAILDIR}/etc/init.d/rc" ] ; then
      if [ -n "${JID}" ] ; then
        jexec ${JID} /bin/sh /etc/init.d/rc 0 2>&1
      fi
    elif [ -e "${JAILDIR}/etc/rc" ] ; then
      if [ -n "${JID}" ] ; then
        jexec ${JID} /bin/sh /etc/rc 0 2>&1
      fi
    fi
  fi
  sleep 3

  umount -f "${JAILDIR}/sys" 2>/dev/null
  umount -f "${JAILDIR}/dev/fd" 2>/dev/null
  umount -f "${JAILDIR}/dev" 2>/dev/null
  umount -f "${JAILDIR}/lib/init/rw" 2>/dev/null
else
  # If we have a custom stop script
  if [ -e "${JMETADIR}/jail-stop" ] ; then
    if [ -n "${JID}" ] ; then
      sCmd=`cat "${JMETADIR}/jail-stop"`
      warden_print "Stopping jail with: ${sCmd}"
      jexec ${JID} ${sCmd} 2>&1
    fi
  else
    if [ -n "${JID}" ] ; then
      warden_print "Stopping jail with: /etc/rc.shutdown"
      jexec ${JID} /bin/sh /etc/rc.shutdown >/dev/null 2>/dev/null
    fi
  fi
fi

umount -f "${JAILDIR}/dev" >/dev/null 2>/dev/null

warden_printf "%s" "."

# Skip the time consuming portion if we are shutting down
if [ "$FAST" != "Y" ]
then

# We asked nicely, so now kill the jail for sure
killall -j ${JID} -TERM 2>/dev/null
sleep 1
killall -j ${JID} -KILL 2>/dev/null

warden_printf "%s" "."

# Check if we need to unmount the devfs in jail
mount | grep "${JAILDIR}/dev" >/dev/null 2>/dev/null
if [ "$?" = "0" ]
then
  # Setup a 60 second timer to try and umount devfs, since takes a bit
  SEC="0"
  while
   i=1
  do
   sleep 2

   # Try to unmount dev
   umount -f "${JAILDIR}/dev" 2>/dev/null
   if [ "$?" = "0" ]
   then
      break
   fi

   SEC="`expr $SEC + 2`"
   warden_printf "%s" "."

   if [ ${SEC} -gt 60 ]
   then
      break
   fi

  done
fi

# Check if we need to unmount any extra dirs
mount | grep "${JAILDIR}/proc" >/dev/null 2>/dev/null
if [ "$?" = "0" ]; then
  umount -f "${JAILDIR}/proc"
fi

if [ -e "${JMETADIR}/jail-portjail" ] ; then
  umountjailxfs "${JAILNAME}"
fi

# Remove any remnant mounts, with force!
for mountpoint in $(mount | grep -e "${JAILDIR}/" | cut -d" " -f3); do
    umount -f "${mountpoint}"
done

fi # End of FAST check

warden_printf "%s" "."

if [ -n "${JID}" ] ; then
  jail -r ${JID}
fi

# post-stop hooks
if [ -x "${JMETADIR}/jail-post-stop" ] ; then
  "${JMETADIR}/jail-post-stop"
fi

warden_printf "%s" "Done"
