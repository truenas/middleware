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
  NETWORKING=0

  if [ -n "${IP4}" -o -n "${IP6}" ] ; then
     NETWORKING=1 
  fi

  if [ "${NETWORKING}" = "1" ] ; then

     # See if we need to create a new bridge, or use an existing one
     _bridges=`get_bridge_interfaces`
     if [ -n "${_bridges}" ] ; then
        for _bridge in ${_bridges}
        do
           _members=`get_bridge_members ${_bridge}`
           for _member in ${_members}
           do 
              if [ "${_member}" = "${IFACE}" ] ; then
                 BRIDGE="${_bridge}"
                 break
              fi
           done
           if [ -n "${BRIDGE}" ] ; then
              break
           fi
        done 
     fi

     if [ -z "${BRIDGE}" ] ; then
        BRIDGE="`ifconfig bridge create mtu ${MTU}`"
     fi 
     if [ -n "${IFACE}" ] ; then
        if ! is_bridge_member "${BRIDGE}" "${IFACE}" ; then
           ifconfig "${BRIDGE}" addm "${IFACE}"
        fi
     fi

     # create epair for vimage jail
     EPAIRA="`ifconfig epair create mtu ${MTU}`"
     ifconfig "${EPAIRA}" up

     EPAIRB="`echo "${EPAIRA}"|sed -E "s/([0-9])a$/\1b/g"`"
     ifconfig "${BRIDGE}" addm "${EPAIRA}" up

     # If no bridge specified, and IP4 is enabled, lets suggest one
     if [ -z "$BRIDGEIP4" -a -n "$IP4" -a "${NATENABLE}" = "YES" ] ; then
        BRIDGEIP4="`echo $IP4 | cut -d '.' -f 1-3`.254"
     fi

     if [ -n "${BRIDGEIP4}" ] ; then
        if ! ipv4_configured "${BRIDGE}" ; then
           ifconfig "${BRIDGE}" inet "${BRIDGEIP4}"

        elif ! ipv4_address_configured "${BRIDGE}" "${BRIDGEIP4}" ; then
           ifconfig "${BRIDGE}" inet alias "${BRIDGEIP4}"
        fi
     fi
     if [ -n "${BRIDGEIPS4}" ] ; then
        for _ip in ${BRIDGEIPS4}
        do
           if ! ipv4_address_configured "${BRIDGE}" "${_ip}" ; then
              ifconfig "${BRIDGE}" inet alias "${_ip}"
           fi 
        done
     fi

     if [ -n "${BRIDGEIP6}" ] ; then
        if ! ipv6_configured "${BRIDGE}" ; then
           ifconfig "${BRIDGE}" inet6 "${BRIDGEIP6}"

        elif ! ipv6_address_configured "${BRIDGE}" "${BRIDGEIP6}" ; then
           ifconfig "${BRIDGE}" inet6 alias "${BRIDGEIP6}"
        fi
     fi
     if [ -n "${BRIDGEIPS6}" ] ; then
        for _ip in ${BRIDGEIPS6}
        do
           if ! ipv6_address_configured "${BRIDGE}" "${_ip}" ; then
              ifconfig "${BRIDGE}" inet6 alias "${_ip}"
           fi
        done
     fi
  fi 

  # Start the jail now
  warden_print "jail -c path=${JAILDIR} name=${HOST} host.hostname=${HOST} ${jFlags} persist vnet=new"
  jail -c path="${JAILDIR}" name="${HOST}" host.hostname="${HOST}" ${jFlags} persist vnet=new
  if [ $? -ne 0 ] ; then
     echo "ERROR: Failed starting jail with above command..."
     umountjailxfs "${JAILNAME}"
     exit 1
  fi

  if [ "${NETWORKING}" = "0" ] ; then
     return 0
  fi

  JID="`jls | grep "${JAILDIR}"$ | tr -s " " | cut -d " " -f 2`"

  #
  # Configure lo0 interface
  #
  jexec ${JID} ifconfig lo0 inet 127.0.0.1 up

  if [ -e "${JMETADIR}/mac" ] ; then
    MAC="$(cat "${JMETADIR}/mac")"
    if [ -n "${MAC}" ] ; then
      ifconfig "${EPAIRB}" ether "${MAC}"
    fi
  else  
    MAC="$(ifconfig "${EPAIRB}" ether|egrep ether|awk '{ print $2 }')"
    if [ -n "${MAC}" ] ; then
      echo "${MAC}" > "${JMETADIR}/mac"
    fi
  fi

  # Set epairb's MTU
  ifconfig ${EPAIRB} mtu ${MTU}

  # Move epairb into jail
  ifconfig "${EPAIRB}" vnet ${JID}

  # Configure the IPv4 addresses
  if [ "${IP4}" = "DHCP" ] ; then
     local ipv4=

     warden_print "Getting IPv4 address from DHCP"
     jexec ${JID} dhclient ${EPAIRB}

     ipv4="$(jexec ${JID} ifconfig ${EPAIRB} inet | \
         grep -w inet|awk '{ print $2 }')"
     arp -s "${ipv4}" "${MAC}"

  elif [ -n "${IP4}" ] ; then
     warden_print "Setting IPv4 address: ${IP4}"
     jexec ${JID} ifconfig ${EPAIRB} inet "${IP4}"
     get_ip_and_netmask "${IP4}"
     arp -s "${JIP}" "${MAC}"
  fi
  for ip4 in ${IPS4}
  do
     ipv4_configured ${EPAIRB} ${JID}
     if [ "$?" = "0" ] ; then
        if ! ipv4_address_configured "${EPAIRB}" "${ip4}" "${JID}" ; then
           jexec ${JID} ifconfig "${EPAIRB}" inet alias "${ip4}"
           get_ip_and_netmask "${ip4}"
           arp -s "${JIP}" "${MAC}"
        fi
     else
        jexec ${JID} ifconfig "${EPAIRB}" inet "${ip4}"
        get_ip_and_netmask "${ip4}"
        arp -s "${JIP}" "${MAC}"
     fi
  done

  # Enable IPv6
  sysrc -j ${JID} inet6_enable="YES"
  sysrc -j ${JID} ip6addrctl_enable="YES"

  # Configure the IPv6 addresses
  if [ "${IP6}" = "AUTOCONF" ] ; then
     sysrc -j ${JID} rtsold_enable="YES"
     sysrc -j ${JID} "ifconfig_${EPAIRB}_ipv6"="inet6 accept_rtadv auto_linklocal"
     #jexec ${JID} service rtsold start

  elif [ -n "${IP6}" ] ; then
     warden_print "Configuring jail for IPv6"

     sysrc -xj ${JID} rtsold_enable
     sysrc -xj ${JID} "ifconfig_${EPAIRB}_ipv6"

     warden_print "Setting IPv6 address: ${IP6}"
     jexec ${JID} ifconfig "${EPAIRB}" inet6 "${IP6}"
  fi
  for ip6 in ${IPS6}
  do
     ipv6_configured ${EPAIRB} ${JID}
     if [ "$?" = "0" ] ; then
        if ! ipv6_address_configured "${EPAIRB}" "${ip6}" "${JID}" ; then
           jexec ${JID} ifconfig "${EPAIRB}" inet6 alias "${ip6}"
        fi
     else
        jexec ${JID} ifconfig "${EPAIRB}" inet6 "${ip6}"
     fi
  done

  #
  # Configure default IPv4 gateway 
  #
  if [ -n "${GATEWAY4}" ] ; then
     local ether="$(arp -na|grep -w "${GATEWAY4}"|awk '{ print $4 }')"
     if [ "${LINUXJAIL}" != "YES" ] ; then
        jexec ${JID} route add default "${GATEWAY4}"
     else
        jexec ${JID} route add default gateway "${GATEWAY4}"
     fi  
     if [ -n "${ether}" ] ; then
        get_ip_and_netmask "${GATEWAY4}"
        jexec ${JID} arp -s "${JIP}" "${ether}"
     fi
  #
  # No defaultrouter configured for IPv4, so if bridge IP address was
  # configured, we set the default router to that IP.
  #
  elif [ -n "${BRIDGEIP4}" ] ; then
     local ether="$(arp -na|grep -w "${GATEWAY4}"|awk '{ print $4 }')"
     get_ip_and_netmask "${BRIDGEIP4}"
     if [ "${LINUXJAIL}" != "YES" ] ; then
        jexec ${JID} route add default "${JIP}"
     else
        jexec ${JID} route add default gateway "${JIP}"
     fi
     if [ -n "${ether}" ] ; then
        get_ip_and_netmask "${BRIDGEIP4}"
        jexec ${JID} arp -s "${JIP}" "${ether}"
     fi
  fi

  #
  # Configure default IPv6 gateway
  #
  if [ -n "${GATEWAY6}" ] ; then
     if [ "${LINUXJAIL}" != "YES" ] ; then
        jexec ${JID} route delete -inet6 default >/dev/null 2>&1
        jexec ${JID} route add -inet6 default "${GATEWAY6}"
     else
        jexec ${JID} route -A inet6 add default gateway "${GATEWAY6}"
     fi 

  #
  # No defaultrouter configured for IPv6, so if bridge IP address was
  # configured, we set the default router to that IP.
  #
  elif [ -n "${BRIDGEIP6}" ] ; then
     get_ip_and_netmask "${BRIDGEIP6}"
     if [ "${LINUXJAIL}" != "YES" ] ; then
        jexec ${JID} route delete -inet6 default >/dev/null 2>&1
        jexec ${JID} route add -inet6 default "${JIP}"
     else
        jexec ${JID} route -A inet6 add default gateway "${JIP}"
     fi
  fi

  #
  # Configure ndp entries for all IPv6 interfaces
  #
  warden_add_ndp_entries "${JID}"

  #
  # If NAT is not enabled, return now
  #
  if [ "${NATENABLE}" = "NO" ] ; then
     if [ -z "${GATEWAY4}" ] ; then
        GATEWAY4="$(get_default_ipv4_route)"
        GATEWAY6="$(get_default_ipv6_route)"
     fi 
     if [ -n "${GATEWAY4}" ] ; then 
        local ether="$(arp -na|grep -w "${GATEWAY4}"|awk '{ print $4 }')"
        if [ "${LINUXJAIL}" != "YES" ] ; then
           jexec ${JID} route add default "${GATEWAY4}"
        else
           jexec ${JID} route add default gateway "${GATEWAY4}"
        fi 
        if [ -n "${ether}" ] ; then
           get_ip_and_netmask "${GATEWAY4}"
           jexec ${JID} arp -s "${JIP}" "${ether}"
        fi
     fi
     if [ -n "${GATEWAY6}" ] ; then 
        if [ "${LINUXJAIL}" != "YES" ] ; then
           echo jexec ${JID} route add default "${GATEWAY6}"
        else
           jexec ${JID} route add default gateway "${GATEWAY6}"
        fi 
     fi

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

  if [ "$(sysrc -n firewall_enable)" != "YES" -o "$(sysrc -n firewall_type)" != "open" ] ; then
     sysrc firewall_enable="YES"
     sysrc firewall_type="open"

     /sbin/ipfw -f flush 
     warden_run ipfw add allow all from any to any via lo0
  fi

  priority=0
  instance=`get_ipfw_nat_instance "${IFACE}"`
  if [ -z "${instance}" ] ; then
     priority=`get_ipfw_nat_priority`
     instance=`get_ipfw_nat_instance`
  else  
     priority=`get_ipfw_nat_priority "${IFACE}"`
     instance=`get_ipfw_nat_instance "${IFACE}"`
  fi

  ext_ip4=`get_interface_ipv4_address "${IFACE}"`
  ext_ip6=`get_interface_ipv6_address "${IFACE}"`

  warden_run ipfw nat "${instance}" config if "${IFACE}" reset same_ports unreg_only log
  if [ -n "${ext_ip4}" ] ; then
     ipfw list | grep -q "from any to "${ext_ip4}" in recv "${IFACE}""
     if [ "$?" != "0" ] ; then
        warden_run ipfw add nat "${instance}" \
           all from any to "${ext_ip4}" in recv "${IFACE}"
     fi
  fi
  if [ -n "${ext_ip6}" ] ; then
     ipfw list | grep -q "from any to "${ext_ip6}" in recv "${IFACE}""
     if [ "$?" != "0" ] ; then
        warden_run ipfw add nat "${instance}" \
           all from any to "${ext_ip6}" in recv "${IFACE}"
     fi
  fi

  if [ -n "${IP4}" ] ; then
     get_ip_and_netmask "${IP4}"
     warden_run ipfw add nat "${instance}" \
        all from "${JIP}" to any out xmit "${IFACE}"
  fi
  for ip4 in ${IPS4}
  do
     get_ip_and_netmask "${ip4}"
     warden_run ipfw add nat "${instance}" \
        all from "${JIP}" to any out xmit "${IFACE}"
  done

  if [ -n "${IP6}" ] ; then
     get_ip_and_netmask "${IP6}"
     warden_run ipfw add nat "${instance}" \
        all from "${JIP}" to any out xmit "${IFACE}"
  fi
  for ip6 in ${IPS6}
  do
     get_ip_and_netmask "${ip6}"
     warden_run ipfw add nat "${instance}" \
        all from "${JIP}" to any out xmit "${IFACE}"
  done

# End of jail VIMAGE startup function
}

# Function to start a jail up the normal way
start_jail_standard()
{
  # Check for primary IPV4 / IPV6
  if [ -n "$IP4" ] ; then
    _ipflags="ip4.addr=${IP4}"
    ifconfig "$IFACE" inet alias "${IP4}"
  fi
  if [ -n "$IP6" ] ; then
    _ipflags="${_ipflags} ip6.addr=${IP6}"
    ifconfig "$IFACE" inet6 alias "${IP6}"
  fi

  # Setup the extra IP4s for this jail
  for _ip in $IPS4
  do
    ifconfig "$IFACE" inet alias "${_ip}"
    _ipflags="${_ipflags} ip4.addr=${_ip}"
  done

  # Setup the extra IP6s for this jail
  for _ip in $IPS6
  do
    ifconfig "$IFACE" inet6 alias "${_ip}"
    _ipflags="${_ipflags} ip6.addr=${_ip}"
  done

  warden_print "jail -c path=${JAILDIR} ${_ipflags} host.hostname=${HOST} ${jFlags} persist"
  jail -c path="${JAILDIR}" ${_ipflags} name="${HOST}" host.hostname="${HOST}" ${jFlags} persist
  if [ $? -ne 0 ] ; then
     warden_error "Failed starting jail with above command..."
     umountjailxfs "${JAILNAME}"
     exit 1
  fi

  JID="`jls | grep "${JAILDIR}"$ | tr -s " " | cut -d " " -f 2`"
}

load_linux_modules()
{
   if ! kldstat|awk '{ print $5 }'|grep -qw linux.ko
   then
      kldload linux >/dev/null 2>&1
   fi

   if ! kldstat|awk '{ print $5 }'|grep -qw linprocfs.ko
   then
      kldload linprocfs >/dev/null 2>&1
   fi

   if ! kldstat|awk '{ print $5 }'|grep -qw linsysfs.ko
   then
      kldload linsysfs >/dev/null 2>&1
   fi

   if ! kldstat|awk '{ print $5 }'|grep -qw lindev.ko
   then
      kldload lindev >/dev/null 2>&1
   fi

   sysctl compat.linux.osrelease=3.9.9
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
jls | grep "${JAILDIR}"$ >/dev/null 2>/dev/null
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
  IFACE="`cat "${JMETADIR}/iface"`"
fi
if [ -z "${IFACE}" ] ; then
   IFACE="`get_default_interface`"
   DEFAULT=1
fi
if [ -z "${IFACE}" ] ; then
  warden_warn "no interface specified and a default doesn't exist!"
fi

MTU=`ifconfig "${IFACE}" | head -1 | sed -E 's/.*mtu ([0-9]+)/\1/g'`

GATEWAY4="$(warden_get_ipv4_defaultrouter)"
GATEWAY6="$(warden_get_ipv6_defaultrouter)"

BRIDGEIP4="$(warden_get_ipv4_bridge)"
BRIDGEIPS4="$(warden_get_ipv4_bridge_aliases)"

BRIDGEIP6="$(warden_get_ipv6_bridge)"
BRIDGEIPS6="$(warden_get_ipv6_bridge_aliases)"

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

if is_linux_jail ; then
   LINUXJAIL="YES"
fi

HOST="`cat "${JMETADIR}/host"`"

if is_symlinked_mountpoint "${JAILDIR}/dev"; then
   warden_print "${JAILDIR}/dev has symlink as parent, not mounting"
else
   mount -t devfs devfs "${JAILDIR}/dev"
   #devfs -m "${JAILDIR}/dev" rule -s 4 applyset
fi

if [ "$LINUXJAIL" = "YES" ] ; then

  # Linux Jail
  load_linux_modules

  if is_symlinked_mountpoint "${JAILDIR}/proc"; then
     warden_print "${JAILDIR}/proc has symlink as parent, not mounting"
  else
     mount -t linprocfs linproc "${JAILDIR}/proc"
  fi
  if is_symlinked_mountpoint "${JAILDIR}/dev/fd"; then
     warden_print "${JAILDIR}/dev/fd has symlink as parent, not mounting"
  else
     mount -t fdescfs null "${JAILDIR}/dev/fd"
  fi
  if is_symlinked_mountpoint "${JAILDIR}/sys"; then
     warden_print "${JAILDIR}/sys has symlink as parent, not mounting"
  else
     mount -t linsysfs linsys "${JAILDIR}/sys"
  fi
  if [ -e "${JAILDIR}/lib/init/rw" ] ; then
    if is_symlinked_mountpoint "${JAILDIR}/lib/init/rw"; then
       warden_print "${JAILDIR}/lib/init/rw has symlink as parent, not mounting"
    else
       mount -t tmpfs tmpfs "${JAILDIR}/lib/init/rw"
    fi
  fi
else
  # FreeBSD Jail
  if is_symlinked_mountpoint "${JAILDIR}/proc"; then
     warden_print "${JAILDIR}/proc has symlink as parent, not mounting"
  else
     mount -t procfs proc "${JAILDIR}/proc"
  fi

  if [ -e "${JMETADIR}/jail-portjail" ] ; then mountjailxfs "${JAILNAME}" ; fi
fi

# Check for user-supplied mounts
if [ -e "${JMETADIR}/fstab" ] ; then
   warden_print "Mounting user-supplied file-systems"
   cat "${JMETADIR}/fstab" \
     | sed "s|%%JAILDIR%%|${JAILDIR}|g" \
     | sort -k 2 > /tmp/.wardenfstab.$$
   mount -a -F /tmp/.wardenfstab.$$
   rm /tmp/.wardenfstab.$$
fi

IP4="$(warden_get_ipv4)"
if [ -n "${IP4}" ] ; then
   # Check if somebody snuck in a IP without / on it
   echo $IP4 | grep -q '/'
   if [ $? -ne 0 -a "${IP4}" != "DHCP" ] ; then
      IP4="${IP4}/24"
   fi
fi

IPS4="$(warden_get_ipv4_aliases)"

IP6="$(warden_get_ipv6)"
if [ -n "${IP6}" ] ; then
   # Check if somebody snuck in a IP without / on it
   echo $IP6 | grep -q '/'
   if [ $? -ne 0 -a "${IP6}" != "AUTOCONF" ] ; then
      IP6="${IP6}/64"
   fi
fi

IPS6="$(warden_get_ipv6_aliases)"

jFlags=""
# Grab any additional jail flags
if [ -e "${JMETADIR}/jail-flags" ] ; then
  jFlags="$(cat "${JMETADIR}"/jail-flags|sed -E 's/,/ /g')"
fi

checkpbiscripts "${JAILDIR}"

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
    sCmd=`cat "${JMETADIR}/jail-start"`
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
    sCmd=`cat "${JMETADIR}/jail-start"`
    warden_print "Starting jail with: ${sCmd}"
    jexec ${JID} ${sCmd} 2>&1
  else
    warden_print "Starting jail with: /etc/rc"
    jexec ${JID} /bin/sh /etc/rc > /dev/null 2>&1
  fi
fi

# Hack. rtsold needs an extra kick for some reason. fukifinoy.
if [ "${VIMAGEENABLE}" = "YES" -a "${IP6}" = "AUTOCONF" ] ; then
   jexec ${JID} service rtsold restart
   warden_add_ndp_entries "${JID}"

elif [ "${VIMAGEENABLE}" = "YES" -a -n "${IP6}" -a -n "${GATEWAY6}" ] ; then
   jexec ${JID} route delete -inet6 default >/dev/null 2>&1
   jexec ${JID} route add -inet6 default "${GATEWAY6}"
   warden_add_ndp_entries "${JID}"
fi

# post-start hooks
if [ -x "${JMETADIR}/jail-post-start" ] ; then
  "${JMETADIR}/jail-post-start"
fi
