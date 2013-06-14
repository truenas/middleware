#/bin/sh
# Script to startup a jail
# Args $1 = jail-name
#######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

start_jail_vimage()
{
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

  # If no bridge specified, and IP4 is enabled, lets suggest one
  if [ -z "$BRIDGEIP4" -a -n "$IP4" ] ; then
     BRIDGEIP4="`echo $IP4 | cut -d '.' -f 1-3`.254"
  fi

  if [ -n "${BRIDGEIP4}" ] ; then
     if ! ipv4_configured "${BRIDGE}" ; then
        ifconfig ${BRIDGE} inet "${BRIDGEIP4}"

     elif ! ipv4_address_configured "${BRIDGE}" "${BRIDGEIP4}" ; then
        ifconfig ${BRIDGE} inet alias "${BRIDGEIP4}"
     fi
  fi
  if [ -n "${BRIDGEIPS4}" ] ; then
     for _ip in ${BRIDGEIPS4}
     do
        if ! ipv4_address_configured "${BRIDGE}" "${_ip}" ; then
           ifconfig ${BRIDGE} inet alias "${_ip}"
        fi 
     done
  fi

  if [ -n "${BRIDGEIP6}" ] ; then
     if ! ipv6_configured "${BRIDGE}" ; then
        ifconfig ${BRIDGE} inet6 "${BRIDGEIP6}"

     elif ! ipv6_address_configured "${BRIDGE}" "${BRIDGEIP6}" ; then
        ifconfig ${BRIDGE} inet6 alias "${BRIDGEIP6}"
     fi
  fi
  if [ -n "${BRIDGEIPS6}" ] ; then
     for _ip in ${BRIDGEIPS6}
     do
        if ! ipv6_address_configured "${BRIDGE}" "${_ip}" ; then
           ifconfig ${BRIDGE} inet6 alias "${_ip}"
        fi
     done
  fi

  # Start the jail now
  warden_print "jail -c path=${JAILDIR} host.hostname=${HOST} ${jFlags} persist vnet"
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
     warden_print "Setting IP4 address: ${IP4}"
     jexec ${JID} ifconfig ${EPAIRB} inet "${IP4}"
  fi
  for ip4 in ${IPS4}
  do
     ipv4_configured ${EPAIRB} ${JID}
     if [ "$?" = "0" ] ; then
        if ! ipv4_address_configured "${EPAIRB}" "${ip4}" "${JID}" ; then
           jexec ${JID} ifconfig ${EPAIRB} inet alias ${ip4}
        fi
     else
        jexec ${JID} ifconfig ${EPAIRB} inet ${ip4}
     fi
  done

  # Configure the IPv6 addresses
  if [ -n "${IP6}" ] ; then
     warden_print "Setting IP6 address: ${IP6}"
     jexec ${JID} ifconfig ${EPAIRB} inet6 "${IP4}"
  fi
  for ip6 in ${IPS6}
  do
     ipv6_configured ${EPAIRB} ${JID}
     if [ "$?" = "0" ] ; then
        if ! ipv6_address_configured "${EPAIRB}" "${ip6}" "${JID}" ; then
           jexec ${JID} ifconfig ${EPAIRB} inet6 alias ${ip6}
        fi
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
  # Configure lo0 interface
  #
  jexec ${JID} ifconfig lo0 up

  #
  # If NAT is not enabled, return now
  #
  if [ "${NATENABLE}" = "NO" ] ; then
      return 0
  fi

  #
  # Set ourself to be a jail router with NAT. Don't
  # use PF since it will panic the box when used
  # with VIMAGE.
  #
  ip_forwarding=`sysctl -n net.inet.ip.forwarding`
  if [ "${ip_forwarding}" = "0" ] ; then
     sysctl net.inet.ip.forwarding=1
  fi

  ip6_forwarding=`sysctl -n net.inet6.ip6.forwarding`
  if [ "${ip6_forwarding}" = "0" ] ; then
     sysctl net.inet6.ip6.forwarding=1
  fi

  firewall_enable=`egrep '^firewall_enable' /etc/rc.conf|cut -f2 -d'='|sed 's|"||g'`
  firewall_type=`egrep '^firewall_type' /etc/rc.conf|cut -f2 -d'='|sed 's|"||g'`

  if [ "${firewall_enable}" != "YES" -o "${firewall_type}" != "open" ] ; then
     tmp_rcconf=`mktemp /tmp/.wdn.XXXXXX`
     egrep -v '^firewall_(enable|type)' /etc/rc.conf >> "${tmp_rcconf}"

     cat<<__EOF__>>"${tmp_rcconf}"
firewall_enable="YES"
firewall_type="open"
__EOF__

     if [ -s "${tmp_rcconf}" ] ; then
        cp /etc/rc.conf /var/tmp/rc.conf.bak
        mv "${tmp_rcconf}" /etc/rc.conf
        if [ "$?" != "0" ] ; then
           mv /var/tmp/rc.conf.bak /etc/rc.conf
        fi
     fi
     /etc/rc.d/ipfw forcerestart
  fi

  instance=`get_ipfw_nat_instance "${IFACE}"`
  if [ -z "${instance}" ] ; then
     priority=`get_ipfw_nat_priority`
     instance=`get_ipfw_nat_instance`

     ipfw "${priority}" add nat "${instance}" all from any to any
     ipfw nat "${instance}" config if "${IFACE}" reset
  fi
# End of jail VIMAGE startup function
}

# Function to start a jail up the normal way
start_jail_standard()
{
  # Check for primary IPV4 / IPV6
  if [ -n "$IP4" ] ; then
    _ipflags="ip4.addr=${IP4}"
    ifconfig $IFACE inet alias ${IP4}
  fi
  if [ -n "$IP6" ] ; then
    _ipflags="${_ipflags} ip6.addr=${IP6}"
    ifconfig $IFACE inet6 alias ${IP6}
  fi

  # Setup the extra IP4s for this jail
  for _ip in $IPS4
  do
    ifconfig $IFACE inet alias ${_ip}
    _ipflags="${_ipflags} ip4.addr=${_ip}"
  done

  # Setup the extra IP6s for this jail
  for _ip in $IPS6
  do
    ifconfig $IFACE inet6 alias ${_ip}
    _ipflags="${_ipflags} ip6.addr=${_ip}"
  done

  warden_print "jail -c path=${JAILDIR} ${_ipflags} host.hostname=${HOST} ${jFlags} persist"
  jail -c path=${JAILDIR} ${_ipflags} host.hostname=${HOST} ${jFlags} persist
  if [ $? -ne 0 ] ; then
     warden_error "Failed starting jail with above command..."
     umountjailxfs "${JAILNAME}"
     exit 1
  fi

  JID="`jls | grep ${JAILDIR}$ | tr -s " " | cut -d " " -f 2`"
}

JAILNAME="${1}"
export JAILNAME

if [ -z "${JAILNAME}" ]
then
  warden_error "No jail specified to start!"
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

# Make sure the jail is NOT already running
jls | grep ${JAILDIR}$ >/dev/null 2>/dev/null
if [ "$?" = "0" ]
then
  warden_error "Jail appears to be running already!"
  exit 6
fi

# pre-start hooks
if [ -x "${JMETADIR}/jail-pre-start" ] ; then
  "${JMETADIR}/jail-pre-start"
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
  warden_error "no interface specified and a default doesn't exist!"
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

# Check if we need to enable vnet
VIMAGEENABLE="NO"
if [ -e "${JMETADIR}/vnet" ] ; then
  VIMAGEENABLE="YES"
fi

# Check if we need to enable NAT
NATENABLE="NO"
if [ -e "${JMETADIR}/nat" ] ; then
  NATENABLE="YES"
fi

set_warden_metadir

if [ -e "${JMETADIR}/jail-linux" ] ; then
   LINUXJAIL="YES"
fi

HOST="`cat ${JMETADIR}/host`"

if is_symlinked_mountpoint ${JAILDIR}/dev; then
   warden_print "${JAILDIR}/dev has symlink as parent, not mounting"
else
   mount -t devfs devfs "${JAILDIR}/dev"
fi

if [ "$LINUXJAIL" = "YES" ] ; then
  # Linux Jail
  if is_symlinked_mountpoint ${JAILDIR}/proc; then
     warden_print "${JAILDIR}/proc has symlink as parent, not mounting"
  else
     mount -t linprocfs linproc "${JAILDIR}/proc"
  fi
  if is_symlinked_mountpoint ${JAILDIR}/dev/fd; then
     warden_print "${JAILDIR}/dev/fd has symlink as parent, not mounting"
  else
     mount -t fdescfs null "${JAILDIR}/dev/fd"
  fi
  if is_symlinked_mountpoint ${JAILDIR}/sys; then
     warden_print "${JAILDIR}/sys has symlink as parent, not mounting"
  else
     mount -t linsysfs linsys "${JAILDIR}/sys"
  fi
  if [ -e "${JAILDIR}/lib/init/rw" ] ; then
    if is_symlinked_mountpoint ${JAILDIR}/lib/init/rw; then
       warden_print "${JAILDIR}/lib/init/rw has symlink as parent, not mounting"
    else
       mount -t tmpfs tmpfs "${JAILDIR}/lib/init/rw"
    fi
  fi
else
  # FreeBSD Jail
  if is_symlinked_mountpoint ${JAILDIR}/proc; then
     warden_print "${JAILDIR}/proc has symlink as parent, not mounting"
  else
     mount -t procfs proc "${JAILDIR}/proc"
  fi

  if [ -e "${JMETADIR}/jail-portjail" ] ; then mountjailxfs ${JAILNAME} ; fi
fi

# Check for user-supplied mounts
if [ -e "${JMETADIR}/fstab" ] ; then
   warden_print "Mounting user-supplied file-systems"
   cp ${JMETADIR}/fstab /tmp/.wardenfstab.$$
   sed -i '' "s|%%JAILDIR%%|${JAILDIR}|g" /tmp/.wardenfstab.$$
   mount -a -F /tmp/.wardenfstab.$$
   rm /tmp/.wardenfstab.$$
fi

IP4=
if [ -e "${JMETADIR}/ipv4" ] ; then
  IP4=`cat "${JMETADIR}/ipv4"`

  # Check if somebody snuck in a IP without / on it
  echo $IP4 | grep -q '/'
  if [ $? -ne 0 ] ; then
     IP4="${IP4}/24"
  fi
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

  # Check if somebody snuck in a IP without / on it
  echo $IP6 | grep -q '/'
  if [ $? -ne 0 ] ; then
     IP6="${IP6}/64"
  fi
fi

IPS6=
if [ -e "${JMETADIR}/alias-ipv6" ] ; then
  while read line
  do
    IPS6="${IPS6} $line" 
  done < ${JMETADIR}/alias-ipv6
fi

jFlags=""
# Grab any additional jail flags
if [ -e "${JMETADIR}/jail-flags" ] ; then
  jFlags=`cat ${JMETADIR}/jail-flags`
fi

# Are we using VIMAGE, if so start it up!
if [ "$VIMAGEENABLE" = "YES" ] ; then
  start_jail_vimage
else
  # Using a standard jail configuration
  start_jail_standard
fi

if [ "$LINUXJAIL" = "YES" ] ; then
  # If we have a custom start script
  if [ -e "${JMETADIR}/jail-start" ] ; then
    sCmd=`cat ${JMETADIR}/jail-start`
    warden_print "Starting jail with: ${sCmd}"
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
    warden_print "Starting jail with: ${sCmd}"
    jexec ${JID} ${sCmd} 2>&1
  else
    warden_print "Starting jail with: /etc/rc"
    jexec ${JID} /bin/sh /etc/rc >/dev/tty 2>&1
  fi
fi

# post-start hooks
if [ -x "${JMETADIR}/jail-post-start" ] ; then
  "${JMETADIR}/jail-post-start"
fi
