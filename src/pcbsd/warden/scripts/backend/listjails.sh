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

lineline=0
VERBOSE="NO"
JAILS=
while [ "$#" -gt "0" ] ; do
  case "$1" in
    -v) VERBOSE="YES" ;; 
     *) JAILS="${JAILS} .$1.meta" ;;
  esac
  shift 
done

if [ "${VERBOSE}" != "YES" ] ; then
# Prints a listing of the available jails
  printf "%-24s%-12s%-12s%-12s\n" ID AUTOSTART STATUS TYPE
  line "75"
fi

cd ${JDIR}
if [ -z "${JAILS}" ] ; then
  JAILS=`ls -d .*.meta 2>/dev/null`
fi

for i in ${JAILS}
do
  AUTO="Disabled" 
  STATUS="<unknown>"

  if [ ! -e "${i}/id" ] ; then
     # Check if its an old-style jail
     if [ ! -e "${i}/ip" ] ; then
       continue
     fi
     # This is an old style jail, lets convert it
     cp ${i}/ip ${i}/ipv4

     # Get next unique ID
     META_ID="$(get_next_id "${JDIR}")"
     echo "$META_ID" > ${i}/id

  fi

  ID="`cat ${i}/id 2>/dev/null`"
  HOST="`cat ${i}/host 2>/dev/null`"

  #
  # IPv4 networking
  # 
  IPS4=
  IP4=`cat ${i}/ipv4 2>/dev/null`
  if [ -e "${i}/alias-ipv4" ] ; then
    while read line
    do
      IPS4="${IPS4} ${line}" 
    done < "${i}/alias-ipv4"
  fi

  BRIDGEIPS4=
  BRIDGEIP4=`cat ${i}/bridge-ipv4 2>/dev/null`
  if [ -e "${i}/alias-bridge-ipv4" ] ; then
    while read line
    do
      BRIDGEIPS4="${BRIDGEIPS4} ${line}" 
    done < "${i}/alias-bridge-ipv4"
  fi

  GATEWAY4=`cat ${i}/defaultrouter-ipv4 2>/dev/null`

  #
  # IPv6 networking
  # 
  IPS6=
  IP6=`cat ${i}/ipv6 2>/dev/null`
  if [ -e "${i}/alias-ipv6" ] ; then
    while read line
    do
      IPS6="${IPS6} ${line}" 
    done < "${i}/alias-ipv6"
  fi

  BRIDGEIPS6=
  BRIDGEIP6=`cat ${i}/bridge-ipv6 2>/dev/null`
  if [ -e "${i}/alias-bridge-ipv6" ] ; then
    while read line
    do
      BRIDGEIPS6="${BRIDGEIPS6} ${line}" 
    done < "${i}/alias-bridge-ipv6"
  fi

  GATEWAY6=`cat ${i}/defaultrouter-ipv6 2>/dev/null`

  # Check if we are autostarting this jail
  if [ -e "${i}/autostart" ] ; then
    AUTO="Enabled"
  fi
 
  # Figure out the type of jail
  if [ -e "${i}/jail-portjail" ] ; then
    TYPE="portjail"
  elif [ -e "${i}/jail-pluginjail" ] ; then
    TYPE="pluginjail"
  elif [ -e "${i}/jail-linux" ] ; then
    TYPE="linuxjail"
  else
    TYPE="standard"
  fi

  JAILNAME=`echo ${i}|sed 's|.meta$||'|sed 's|^.||'`

  ${PROGDIR}/scripts/backend/checkstatus.sh ${JAILNAME} 2>/dev/null
  if [ "$?" = "0" ]
  then
    STATUS="Running"
  else
    STATUS="Stopped"
  fi

  if [ "${VERBOSE}" = "YES" ] ; then
    cat<<__EOF__ 

id: ${ID}
host: ${HOST}
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
status: ${STATUS}
type: ${TYPE}

__EOF__

  else
    printf "%-24s%-12s%-12s%-12s\n" ${JAILNAME} ${AUTO} ${STATUS} ${TYPE}
  fi
done

