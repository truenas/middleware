#!/bin/sh
# Prints a listing of the installed jails
######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

# Check if we have any jails
if [ ! -d "${JDIR}" ]
then
  echo "Error: No jails found!"
  exit 4
fi

line()
{
  len="${1}"

  i=0 
  while [ "${i}" -lt "${len}" ] ; do
    i=`expr ${i} + 1`
    echo -n '-' 
  done
  echo 
}

ifs="${IFS}"
IFS=$'\n'

lineline=0
VERBOSE="NO"

NJAILS=0
while [ "$#" -gt "0" ] ; do
  case "$1" in
    -v) VERBOSE="YES" ;; 
     *) var="jail_${NJAILS}"
        val=".${1}.meta"
        eval "${var}='${val}'"
        : $(( NJAILS += 1 ))
        ;;  
  esac
  shift 
done

if [ "${VERBOSE}" != "YES" ] ; then
# Prints a listing of the available jails
  warden_printf "%-24s %-12s %-12s %-12s\n" ID AUTOSTART STATUS TYPE
  warden_printf "%s\n" $(line "75")
fi

cd "${JDIR}"
if [ -z "${NJAILS}" -o "${NJAILS}" = "0" ]; then
  NJAILS=0
  for j in $(ls -d .*.meta 2>/dev/null)
  do
     var="jail_${NJAILS}"
     eval "${var}='${j}'"
     : $(( NJAILS += 1 ))
  done
fi

i=0
while [ "${i}" -lt "${NJAILS}" ]
do
  var=\$$(printf "jail_${i}")
  jail="$(eval "echo ${var} 2>/dev/null")"
  : $(( i += 1 ))

  jailfp="$(realpath "${jail}")"

  AUTO="Disabled" 
  STATUS="<unknown>"

  if [ ! -e "${jail}/id" ] ; then
     # Check if its an old-style jail
     if [ ! -e "${jail}/ip" ] ; then
        continue 
     fi

     # This is an old style jail, lets convert it
     cp ${jail}/ip ${jail}/ipv4

     # Get next unique ID
     META_ID="$(get_next_id "${JDIR}")"
     echo "$META_ID" > ${jail}/id
  fi

  ID="$(warden_get_id "${jailfp}")"
  if [ -z "${ID}" ]
  then
    continue
  fi

  if [ "$(eval echo \$__usedjid${ID})" = "true" ]; then
    ID="$(get_next_id "${JDIR}")"
    echo "$ID" > ${jail}/id
  else
    eval __usedjid${ID}=true
  fi

  HOST="$(warden_get_host "${jailfp}")"
  JAILNAME=`echo ${jail}|sed 's|.meta$||'|sed 's|^.||'`

  if warden_vnet_enabled "${jailfp}" ; then
    VNET="Enabled"
  else
    VNET="Disabled"
  fi

  IFACE="$(warden_get_iface "${jailfp}")"

  if warden_nat_enabled "${jailfp}" ; then
    NAT="Enabled"
  else
    NAT="Disabled"
  fi

  MAC="$(warden_get_mac "${jailfp}")"

  #
  # IPv4 networking
  # 
  IP4="$(warden_get_ipv4 "${jailfp}")"
  IPS4="$(warden_get_ipv4_aliases "${jailfp}")"
  BRIDGEIP4="$(warden_get_ipv4_bridge "${jailfp}")"
  BRIDGEIPS4="$(warden_get_ipv4_bridge_aliases "${jailfp}")"
  GATEWAY4="$(warden_get_ipv4_defaultrouter "${jailfp}")"

  if [ "${IP4}" = "DHCP" ] && warden_jail_isrunning "${JAILNAME}" ; then
     JID="$(warden_get_jailid "${JAILNAME}")"
     IFACE="$(get_default_ipv4_interface "${JID}")"

     IP4="DHCP"
     if [ -n "${IFACE}" ] ; then
        ADDR="$(get_interface_ipv4_address "${IFACE}" "${JID}")"
        if [ -n "${ADDR}" ] ; then
           IP4="${IP4}:${ADDR}"
        fi
     fi

     if [ -z "${GATEWAY4}" ] ; then
        GATEWAY4="DHCP"
        ADDR="$(get_default_ipv4_route "${JID}")"
        if [ -n "${ADDR}" ] ; then
           GATEWAY4="${GATEWAY4}:${ADDR}"
        fi
     fi
  fi 

  #
  # IPv6 networking
  # 
  IP6="$(warden_get_ipv6 "${jailfp}")"
  IPS6="$(warden_get_ipv6_aliases "${jailfp}")"
  BRIDGEIP6="$(warden_get_ipv6_bridge "${jailfp}")"
  BRIDGEIPS6="$(warden_get_ipv6_bridge_aliases "${jailfp}")"
  GATEWAY6="$(warden_get_ipv6_defaultrouter "${jailfp}")"

  if [ "${IP6}" = "AUTOCONF" ] && warden_jail_isrunning "${JAILNAME}" ; then
     JID="$(warden_get_jailid "${JAILNAME}")"
     IFACE="$(get_default_ipv6_interface "${JID}")"

     IP6="AUTOCONF"
     if [ -n "${IFACE}" ] ; then
        ADDR="$(get_interface_ipv6_address "${IFACE}" "${JID}")"
        if [ -n "${ADDR}" ] ; then
           IP6="${IP6}:${ADDR}" 
        fi
     fi

     if [ -z "${GATEWAY6}" ] ; then
        GATEWAY6="AUTOCONF"
        ADDR="$(get_default_ipv6_route "${JID}")"
        if [ -n "${ADDR}" ] ; then
           GATEWAY6="${GATEWAY6}:${ADDR}" 
        fi
     fi
  fi 

  # Check if we are autostarting this jail
  if warden_autostart_enabled "${jailfp}" ; then
    AUTO="Enabled"
  fi
 
  # Figure out the type of jail
  if [ -e "${jail}/jail-portjail" ] ; then
    echo portjail > "${jail}/jailtype"
    rm -f "${jail}/jail-portjail"
  elif [ -e "${jail}/jail-pluginjail" ] ; then
    echo pluginjail > "${jail}/jailtype"
    rm -f "${jail}/jail-pluginjail"
  elif [ -e "${jail}/jail-linux" ] ; then
    TYPE="$(cat "${jail}/jail-linux")"
    if [ -z "${TYPE}" ] ; then
      TYPE="linuxjail"
    fi
    echo "${TYPE}" > "${jail}/jailtype"
    rm -f "${jail}/jail-linux"
  fi

  TYPE="$(warden_get_jailtype "${jailfp}")"
  if [ -z "${TYPE}" ] ; then 
    TYPE="standard"
    echo "${TYPE}" > "${jail}/jailtype"
  fi

  ${PROGDIR}/scripts/backend/checkstatus.sh "${JAILNAME}" 2>/dev/null
  if [ "$?" = "0" ]
  then
    STATUS="Running"
  else
    STATUS="Stopped"
  fi

  FLAGS="$(warden_get_jailflags "${jailfp}")"

  if [ "${VERBOSE}" = "YES" ] ; then
    out="$(mktemp  /tmp/.wjvXXXXXX)"
    cat<<__EOF__ >"${out}"

id: ${ID}
host: ${HOST}
iface: ${IFACE}
ipv4: ${IP4}
alias-ipv4: ${IPS4}
bridge-ipv4: ${BRIDGEIP4}
alias-bridge-ipv4: ${BRIDGEIPS4}
defaultrouter-ipv4: ${GATEWAY4}
ipv6: ${IP6}
alias-ipv6: ${IPS6}
bridge-ipv6: ${BRIDGEIP6}
alias-bridge-ipv6: ${BRIDGEIPS6}
defaultrouter-ipv6: ${GATEWAY6}
autostart: ${AUTO}
vnet: ${VNET}
nat: ${NAT}
mac: ${MAC}
status: ${STATUS}
type: ${TYPE}
flags: ${FLAGS}

__EOF__

    warden_cat "${out}"
    rm -f "${out}"

  else
    warden_printf "%-24s %-12s %-12s %-12s\n" "${JAILNAME}" ${AUTO} ${STATUS} ${TYPE}
  fi

done
IFS="${ifs}"
