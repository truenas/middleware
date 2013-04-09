#/bin/sh
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

MTU=`ifconfig ${IFACE} | head -1 | sed -E 's/.*mtu ([0-9]+)/\1/g'`

GATEWAY4=
if [ -e "${JMETADIR}/defaultrouter-ipv4" ] ; then
  GATEWAY4=`cat "${JMETADIR}/defaultrouter-ipv4"`
fi
GATEWAY6=
if [ -e "${JMETADIR}/defaultrouter-ipv6" ] ; then
  GATEWAY6=`cat "${JMETADIR}/defaultrouter-ipv6"`
fi

BRIDGEIP4=
if [ -e "${JMETADIR}/bridge-ipv4" ] ; then
  BRIDGEIP4=`cat "${JMETADIR}/bridge-ipv4"`
fi

BRIDGEIPS4=
if [ -e "${JMETADIR}/alias-bridge-ipv4" ] ; then
  while read line
  do
    BRIDGEIPS4="${BRIDGEIPS4} $line" 
  done < ${JMETADIR}/alias-bridge-ipv4
fi

BRIDGEIP6=
if [ -e "${JMETADIR}/bridge-ipv6" ] ; then
  BRIDGEIP6=`cat "${JMETADIR}/bridge-ipv6"`
fi

BRIDGEIPS6=
if [ -e "${JMETADIR}/alias-bridge-ipv6" ] ; then
  while read line
  do
    BRIDGEIPS6="${BRIDGEIPS6} $line" 
  done < ${JMETADIR}/alias-bridge-ipv6
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

IP4=
if [ -e "${JMETADIR}/ipv4" ] ; then
  IP4=`cat "${JMETADIR}/ipv4"`
fi

IPS4=
if [ -e "${JMETADIR}/alias-ipv4" ] ; then
  while read line
  do
    IPS4="${IPS4} $line" 
  done < ${JMETADIR}/alias-ipv4
fi

IP6=
if [ -e "${JMETADIR}/ipv6" ] ; then
  IP6=`cat "${JMETADIR}/ipv6"`
fi

IPS6=
if [ -e "${JMETADIR}/alias-ipv6" ] ; then
  while read line
  do
    IPS6="${IPS6} $line" 
  done < ${JMETADIR}/alias-ipv6
fi

BRIDGE=

# See if we need to create a new bridge, or use an existing one
_bridges=`get_bridge_interfaces`
if [ -n "${_bridges}" ] ; then
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

if [ -z "${BRIDGE}" ] ; then
   BRIDGE=`ifconfig bridge create mtu ${MTU}`
fi
if [ -n "${IFACE}" ] ; then
   if ! is_bridge_member "${BRIDGE}" "${IFACE}" ; then
      ifconfig ${BRIDGE} addm ${IFACE}
   fi
fi

# create epair for vimage jail
EPAIRA=`ifconfig epair create mtu ${MTU}`
ifconfig ${EPAIRA} up

EPAIRB=`echo ${EPAIRA}|sed -E "s/([0-9])a$/\1b/g"`
ifconfig ${BRIDGE} addm ${EPAIRA} up

if [ -n "${BRIDGEIP4}" ] ; then
   if ! ipv4_configured "${BRIDGE}" ; then
      ifconfig ${BRIDGE} inet "${BRIDGEIP4}"
   else
      ifconfig ${BRIDGE} inet alias "${BRIDGEIP4}"
   fi
fi
if [ -n "${BRIDGEIPS4}" ] ; then
   for _ip in ${BRIDGEIPS4}
   do
      ifconfig ${BRIDGE} inet alias "${_ip}"
   done
fi

if [ -n "${BRIDGEIP6}" ] ; then
   if ! ipv6_configured "${BRIDGE}" ; then
      ifconfig ${BRIDGE} inet6 "${BRIDGEIP6}"
   else
      ifconfig ${BRIDGE} inet6 alias "${BRIDGEIP6}"
   fi
fi
if [ -n "${BRIDGEIPS6}" ] ; then
   for _ip in ${BRIDGEIPS6}
   do
      ifconfig ${BRIDGE} inet6 alias "${_ip}"
   done
fi

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
   umountjailxfs "${JAILNAME}"
   exit 1
fi

JID="`jls | grep ${JAILDIR}$ | tr -s " " | cut -d " " -f 2`"

# Move epairb into jail
ifconfig ${EPAIRB} vnet ${JID}

# Configure the IPv4 addresses
if [ -n "${IP4}" ] ; then
   jexec ${JID} ifconfig ${EPAIRB} inet "${IP4}"
fi
for ip4 in ${IPS4}
do
   ipv4_configured ${EPAIRB} ${JID}
   if [ "$?" = "0" ] ; then
      jexec ${JID} ifconfig ${EPAIRB} inet alias ${ip4}
   else
      jexec ${JID} ifconfig ${EPAIRB} inet ${ip4}
   fi
done

# Configure the IPv6 addresses
if [ -n "${IP6}" ] ; then
   jexec ${JID} ifconfig ${EPAIRB} inet6 "${IP4}"
fi
for ip6 in ${IPS6}
do
   ipv6_configured ${EPAIRB} ${JID}
   if [ "$?" = "0" ] ; then
      jexec ${JID} ifconfig ${EPAIRB} inet6 alias ${ip6}
   else
      jexec ${JID} ifconfig ${EPAIRB} inet6 ${ip6}
   fi
done

#
# Configure default IPv4 gateway 
#
if [ -n "${GATEWAY4}" ] ; then
   jexec ${JID} route add -inet default ${GATEWAY4}

#
# No defaultrouter configured for IPv4, so if bridge IP address was
# configured, we set the default router to that IP.
#
elif [ -n "${BRIDGEIP4}" ] ; then
   get_ip_and_netmask "${BRIDGEIP4}"
   jexec ${JID} route add -inet default ${JIP}
fi

#
# Configure default IPv6 gateway
#
if [ -n "${GATEWAY6}" ] ; then
   jexec ${JID} route add -inet6 default ${GATEWAY6}

#
# No defaultrouter configured for IPv6, so if bridge IP address was
# configured, we set the default router to that IP.
#
elif [ -n "${BRIDGEIP6}" ] ; then
   get_ip_and_netmask "${BRIDGEIP6}"
   jexec ${JID} route add -inet6 default ${JIP}
fi

#
# Set ourself to be a jail router with NAT. Don't
# use PF since it will panic the box when used
# with VIMAGE.
#
sysctl net.inet.ip.forwarding=1
sysctl net.inet6.ip6.forwarding=1

tmp_rcconf=`mktemp /tmp/.wdn.XXXXXX`

egrep -v '^(firewall_(enable|type)|natd_(enable|interface|flags))' \
   /etc/rc.conf >> "${tmp_rcconf}"
cat<<__EOF__>>"${tmp_rcconf}"
firewall_enable="YES"
firewall_type="open"
natd_enable="YES"
natd_interface="${IFACE}"
natd_flags="-dynamic -m"
__EOF__
if [ -s "${tmp_rcconf}" ] ; then
   cp /etc/rc.conf /var/tmp/rc.conf.bak
   mv "${tmp_rcconf}" /etc/rc.conf
   if [ "$?" != "0" ] ; then
      mv /var/tmp/rc.conf.bak /etc/rc.conf
   fi
fi

ipfw list | grep -Eq '^00500 divert' 2>/dev/null
if [ "$?" != "0" ] ; then
   /etc/rc.d/ipfw restart
   ipfw -q add 00050 divert 8668 ip4 from any to any via ${IFACE}
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
