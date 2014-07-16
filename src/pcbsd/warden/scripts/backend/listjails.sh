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
  warden_printf "%-24s%-12s%-12s%-12s\n" ID AUTOSTART STATUS TYPE
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

  ID="`cat "${jail}/id" 2>/dev/null`"
  if [ -z "${ID}" ]
  then
    continue
  fi  

  HOST="`cat "${jail}/host" 2>/dev/null`"
  if [ -e "${jail}/vnet" ] ; then
    VNET="Enabled"
  else
    VNET="Disabled"
  fi

  IFACE="`cat "${jail}/iface" 2>/dev/null`"

  if [ -e "${jail}/nat" ] ; then
    NAT="Enabled"
  else
    NAT="Disabled"
  fi

  MAC=
  if [ -e "${jail}/mac" ] ; then
     MAC="`cat "${jail}/mac"`"
  fi 

  #
  # IPv4 networking
  # 
  IPS4=
  IP4=`cat "${jail}/ipv4" 2>/dev/null`
  if [ -e "${jail}/alias-ipv4" ] ; then
    while read line
    do
      IPS4="${IPS4} ${line}" 
    done < "${jail}/alias-ipv4"
  fi

  BRIDGEIPS4=
  BRIDGEIP4=`cat "${jail}/bridge-ipv4" 2>/dev/null`
  if [ -e "${jail}/alias-bridge-ipv4" ] ; then
    while read line
    do
      BRIDGEIPS4="${BRIDGEIPS4} ${line}" 
    done < "${jail}/alias-bridge-ipv4"
  fi

  GATEWAY4=`cat "${jail}/defaultrouter-ipv4" 2>/dev/null`

  #
  # IPv6 networking
  # 
  IPS6=
  IP6=`cat "${jail}/ipv6" 2>/dev/null`
  if [ -e "${jail}/alias-ipv6" ] ; then
    while read line
    do
      IPS6="${IPS6} ${line}" 
    done < "${jail}/alias-ipv6"
  fi

  BRIDGEIPS6=
  BRIDGEIP6=`cat "${jail}/bridge-ipv6" 2>/dev/null`
  if [ -e "${jail}/alias-bridge-ipv6" ] ; then
    while read line
    do
      BRIDGEIPS6="${BRIDGEIPS6} ${line}" 
    done < "${jail}/alias-bridge-ipv6"
  fi

  GATEWAY6=`cat "${jail}/defaultrouter-ipv6" 2>/dev/null`

  # Check if we are autostarting this jail
  if [ -e "${jail}/autostart" ] ; then
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

  TYPE="$(cat "${jail}/jailtype")"
  if [ -z "${TYPE}" ] ; then 
    TYPE="standard"
    echo "${TYPE}" > "${jail}/jailtype"
  fi

  JAILNAME=`echo ${jail}|sed 's|.meta$||'|sed 's|^.||'`

  ${PROGDIR}/scripts/backend/checkstatus.sh "${JAILNAME}" 2>/dev/null
  if [ "$?" = "0" ]
  then
    STATUS="Running"
  else
    STATUS="Stopped"
  fi

  FLAGS=
  if [ -s "${jail}/jail-flags" ]
  then
    FLAGS="$(cat "${jail}/jail-flags"|tr ' ' ',')"
  fi

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
    warden_printf "%-24s%-12s%-12s%-12s\n" "${JAILNAME}" ${AUTO} ${STATUS} ${TYPE}
  fi

done
IFS="${ifs}"
