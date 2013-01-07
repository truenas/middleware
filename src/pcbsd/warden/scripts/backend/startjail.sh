#!/bin/sh
# Script to startup a jail
# Args $1 = jail-name
#######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

JAILNAME="${1}"

if [ -z "${JAILNAME}" ]
then
  echo "ERROR: No jail specified to start!"
  exit 5
fi

if [ -z "${JDIR}" ]
then
  echo "ERROR: JDIR is unset!!!!"
  exit 5
fi

JAILDIR="${JDIR}/${JAILNAME}"

if [ ! -d "${JAILDIR}" ]
then
  echo "ERROR: No jail located at ${JAILDIR}"
  exit 5
fi

# Make sure the jail is NOT already running
jls | grep ${JAILDIR}$ >/dev/null 2>/dev/null
if [ "$?" = "0" ]
then
  echo "ERROR: Jail appears to be running already!"
  exit 6
fi

IFACE=
DEFAULT=0

# Make sure jail uses special interface if specified
if [ -e "${JMETADIR}/iface" ] ; then
  IFACE=`cat "${JMETADIR}/iface"`
fi
if [ -z "${IFACE}" ] ; then
   IFACE=`get_default_interface`
   DEFAULT=1
fi
if [ -z "${IFACE}" ] ; then
  echo "ERROR: no interface specified and a default doesn't exist!"
  exit 6
fi

GATEWAY=
MTU=`ifconfig ${IFACE} | head -1 | sed -E 's/.*mtu ([0-9]+)/\1/g'`

# Determine gateway to use for this jail
for _ip in `get_interface_addresses ${IFACE}`
do
   for _gw in `netstat -f inet -nr | grep ${IFACE} | awk '{ print $2 }'`
   do
      if [ "${_gw}" = "${_ip}" ] ; then
         GATEWAY="${_ip}"
         break
      fi
   done
   if [ -n "${GATEWAY}" ] ; then
      break
   fi
done
if [ -z "${GATEWAY}" -a "${DEFAULT}" = "1" ] ; then
   GATEWAY=`get_default_route`
fi

set_warden_metadir

if [ -e "${JMETADIR}/jail-linux" ] ; then
   LINUXJAIL="YES"
fi

HOST="`cat ${JMETADIR}/host`"

if is_symlinked_mountpoint ${JAILDIR}/dev; then
   echo "${JAILDIR}/dev has symlink as parent, not mounting"
else
   mount -t devfs devfs "${JAILDIR}/dev"
fi

if [ "$LINUXJAIL" = "YES" ] ; then
  # Linux Jail
  if is_symlinked_mountpoint ${JAILDIR}/proc; then
     echo "${JAILDIR}/proc has symlink as parent, not mounting"
  else
     mount -t linprocfs linproc "${JAILDIR}/proc"
  fi
  if is_symlinked_mountpoint ${JAILDIR}/dev/fd; then
     echo "${JAILDIR}/dev/fd has symlink as parent, not mounting"
  else
     mount -t fdescfs null "${JAILDIR}/dev/fd"
  fi
  if is_symlinked_mountpoint ${JAILDIR}/sys; then
     echo "${JAILDIR}/sys has symlink as parent, not mounting"
  else
     mount -t linsysfs linsys "${JAILDIR}/sys"
  fi
  if [ -e "${JAILDIR}/lib/init/rw" ] ; then
    if is_symlinked_mountpoint ${JAILDIR}/lib/init/rw; then
       echo "${JAILDIR}/lib/init/rw has symlink as parent, not mounting"
    else
       mount -t tmpfs tmpfs "${JAILDIR}/lib/init/rw"
    fi
  fi
else
  # FreeBSD Jail
  if is_symlinked_mountpoint ${JAILDIR}/proc; then
     echo "${JAILDIR}/proc has symlink as parent, not mounting"
  else
     mount -t procfs proc "${JAILDIR}/proc"
  fi

  if [ -e "${JMETADIR}/jail-portjail" ] ; then mountjailxfs ${JAILNAME} ; fi
fi

IPS=
if [ -e "${JMETADIR}/ip" ] ; then
  IPS=`cat "${JMETADIR}/ip"`
fi

if [ -e "${JMETADIR}/ip-extra" ] ; then
  while read line
  do
    IPS="${IPS} $line" 
  done < ${JMETADIR}/ip-extra
fi

BRIDGE=

# See if we need to create a new bridge, or use an existing one
_bridges=`get_bridge_interfaces`
if [ -n ${_bridges} ] ; then
   for _bridge in ${_bridges}
   do
      _members=`get_bridge_members ${_bridge}`
      for _member in ${_members}
      do 
         if [ "${_member}" = "${IFACE}" ] ; then
            BRIDGE=${_bridge}
            break
         fi
      done
      if [ -n "${BRIDGE}" ] ; then
         break
      fi
   done 
fi
BRIDGE=bridge0

if [ -z "${BRIDGE}" ] ; then
   echo ifconfig bridge create mtu ${MTU}
   BRIDGE=`ifconfig bridge create mtu ${MTU}`
fi
if [ -n "${IFACE}" ] ; then
   echo ifconfig ${BRIDGE} addm ${IFACE}
   ifconfig ${BRIDGE} addm ${IFACE}
fi

i=0
npairs=0

# create an epair for every IP address specified
for _ip in ${IPS}
do
   eval "ip${i}='${_ip}'"
 
   _epair=`ifconfig epair create mtu ${MTU}`
   eval "epair${i}='${_epair}'"

   echo ifconfig ${_epair} up
   ifconfig ${_epair} up

   _epairb=`echo ${_epair}|sed -E "s/([0-9])a$/\1b/g"`
   eval "epairb${i}='${_epairb}'"

   echo ifconfig ${BRIDGE} addm ${_epair} up
   ifconfig ${BRIDGE} addm ${_epair} up

   : $((i += 1))
done
npairs=${i}

# Setup the IPs for this jail
#for _ip in $IPS
#do
#  isV6 "${_ip}"
#  if [ $? -eq 0 ] ; then
#    ifconfig $NIC inet6 alias ${_ip}
#    _ipflags="${_ipflags} ip6.addr=${_ip}"
#  else
#    ifconfig $NIC inet alias ${_ip}/32
#    _ipflags="${_ipflags} ip4.addr=${_ip}"
#  fi
#done

jFlags=""
# Grab any additional jail flags
if [ -e "${JMETADIR}/jail-flags" ] ; then
  jFlags=`cat ${JMETADIR}/jail-flags`
fi

# Start the jail now
echo "jail -c path=${JAILDIR} host.hostname=${HOST} ${jFlags} persist vnet"
jail -c path=${JAILDIR} host.hostname=${HOST} ${jFlags} persist vnet
if [ $? -ne 0 ] ; then
   echo "ERROR: Failed starting jail with above command..."

   # Do cleanup now
#   isV6 "${_ip}"
#   if [ $? -eq 0 ] ; then
#      ifconfig $NIC inet6 ${_ip} delete
#   else
#      ifconfig $NIC inet -alias ${_ip}
#   fi
   umountjailxfs "${JAILNAME}"
   exit 1
fi

JID="`jls | grep ${JAILDIR}$ | tr -s " " | cut -d " " -f 2`"


# Configure the IP addresses now
i=0
while [ "${i}" -lt "${npairs}" ]
do
   _var="\$epairb${i}"
   _epairb=`eval "echo ${_var} 2>/dev/null"`

   _var="\$ip${i}"
   _ip=`eval "echo \${_var} 2>/dev/null"`

   echo ifconfig ${_epairb} vnet ${JID}
   ifconfig ${_epairb} vnet ${JID}

   get_ip_and_netmask "${_ip}"

   isV6 "${JIP}"
   if [ "$?" = "0" ] ; then
      echo jexec ${JID} ifconfig ${_epairb} inet6 ${_ip}
      jexec ${JID} ifconfig ${_epairb} inet6 ${_ip}
   else
      echo jexec ${JID} ifconfig ${_epairb} inet ${_ip}
      jexec ${JID} ifconfig ${_epairb} inet ${_ip}
   fi

   : $((i += 1))
done

if [ -n "${GATEWAY}" ] ; then
   echo jexec ${JID} route add default ${GATEWAY}
   jexec ${JID} route add default ${GATEWAY}
fi

if [ "$LINUXJAIL" = "YES" ] ; then
  # If we have a custom start script
  if [ -e "${JMETADIR}/jail-start" ] ; then
    sCmd=`cat ${JMETADIR}/jail-start`
    echo "Starting jail with: ${sCmd}"
    jexec ${JID} ${sCmd} 2>&1
  else
    # Check for different init styles
    if [ -e "${JAILDIR}/etc/init.d/rc" ] ; then
      jexec ${JID} /bin/sh /etc/init.d/rc 3 2>&1
    elif [ -e "${JAILDIR}/etc/rc" ] ; then
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
