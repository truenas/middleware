#!/bin/sh
# Script to startup a jail
# Args $1 = jail-dir
#######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

IP="${1}"

if [ -z "${IP}" ]
then
  echo "ERROR: No jail specified to start!"
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

# Check if we have a valid NIC
ifconfig $NIC 2>/dev/null >/dev/null
if [ $? -ne 0 ] ; then
   echo "ERROR: Invalid network interface specified: $NIC"
   exit 6
fi

# Make sure the jail is NOT already running
jls | grep ${JDIR}/${IP}$ >/dev/null 2>/dev/null
if [ "$?" = "0" ]
then
  echo "ERROR: Jail appears to be running already!"
  exit 6
fi

set_warden_metadir

if [ -e "${JMETADIR}/jail-linux" ] ; then
   LINUXJAIL="YES"
fi

HOST="`cat ${JMETADIR}/host`"

if is_symlinked_mountpoint ${JDIR}/${IP}/dev; then
   echo "${JDIR}/${IP}/dev has symlink as parent, not mounting"
else
   mount -t devfs devfs "${JDIR}/${IP}/dev"
fi

if [ "$LINUXJAIL" = "YES" ] ; then
  # Linux Jail
  if is_symlinked_mountpoint ${JDIR}/${IP}/proc; then
     echo "${JDIR}/${IP}/proc has symlink as parent, not mounting"
  else
     mount -t linprocfs linproc "${JDIR}/${IP}/proc"
  fi
  if is_symlinked_mountpoint ${JDIR}/${IP}/dev/fd; then
     echo "${JDIR}/${IP}/dev/fd has symlink as parent, not mounting"
  else
     mount -t fdescfs null "${JDIR}/${IP}/dev/fd"
  fi
  if is_symlinked_mountpoint ${JDIR}/${IP}/sys; then
     echo "${JDIR}/${IP}/sys has symlink as parent, not mounting"
  else
     mount -t linsysfs linsys "${JDIR}/${IP}/sys"
  fi
  if [ -e "${JDIR}/${IP}/lib/init/rw" ] ; then
    if is_symlinked_mountpoint ${JDIR}/${IP}/lib/init/rw; then
       echo "${JDIR}/${IP}/lib/init/rw has symlink as parent, not mounting"
    else
       mount -t tmpfs tmpfs "${JDIR}/${IP}/lib/init/rw"
    fi
  fi
else
  # FreeBSD Jail
  if is_symlinked_mountpoint ${JDIR}/${IP}/proc; then
     echo "${JDIR}/${IP}/proc has symlink as parent, not mounting"
  else
     mount -t procfs proc "${JDIR}/${IP}/proc"
  fi

  if [ -e "${JMETADIR}/jail-portjail" ] ; then mountjailxfs ${IP} ; fi
fi

IPS="${IP}"
if [ -e "${JMETADIR}/ip-extra" ] ; then
  while read line
  do
    IPS="${IPS} $line" 
  done < ${JMETADIR}/ip-extra
fi

# Setup the IPs for this jail
for _ip in $IPS
do
  isV6 "${_ip}"
  if [ $? -eq 0 ] ; then
    ifconfig $NIC inet6 alias ${_ip}
    _ipflags="${_ipflags} ip6.addr=${_ip}"
  else
    ifconfig $NIC inet alias ${_ip}/32
    _ipflags="${_ipflags} ip4.addr=${_ip}"
  fi
done

jFlags=""
# Grab any additional jail flags
if [ -e "${JMETADIR}/jail-flags" ] ; then
  jFlags=`cat ${JMETADIR}/jail-flags`
fi

# Start the jail now
echo "jail -c path=${JDIR}/${IP} host.hostname=${HOST} ${_ipflags} ${jFlags} persist"
jail -c path=${JDIR}/${IP} host.hostname=${HOST} ${_ipflags} ${jFlags} persist
if [ $? -ne 0 ] ; then
   echo "ERROR: Failed starting jail with above command..."

   # Do cleanup now
   isV6 "${_ip}"
   if [ $? -eq 0 ] ; then
      ifconfig $NIC inet6 ${_ip} delete
   else
      ifconfig $NIC inet -alias ${_ip}
   fi
   umountjailxfs "${IP}"
   exit 1
fi

JID="`jls | grep ${JDIR}/${IP}$ | tr -s " " | cut -d " " -f 2`"

if [ "$LINUXJAIL" = "YES" ] ; then
  # If we have a custom start script
  if [ -e "${JMETADIR}/jail-start" ] ; then
    sCmd=`cat ${JMETADIR}/jail-start`
    echo "Starting jail with: ${sCmd}"
    jexec ${JID} ${sCmd} 2>&1
  else
    # Check for different init styles
    if [ -e "${JDIR}/${IP}/etc/init.d/rc" ] ; then
      jexec ${JID} /bin/sh /etc/init.d/rc 3 2>&1
    elif [ -e "${JDIR}/${IP}/etc/rc" ] ; then
      jexec ${JID} /bin/sh /etc/rc 3 2>&1
    fi
  fi
else
  # If we have a custom start script
  if [ -e "${JMETADIR}/jail-start" ] ; then
    sCmd=`cat ${JMETADIR}/jail-start`
    echo "Starting jail with: ${sCmd}"
    jexec ${JID} ${sCmd} 2>&1
  else
    echo "Starting jail with: /etc/rc"
    jexec ${JID} /bin/sh /etc/rc 2>&1
  fi
fi

