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

SHOW_IDS="${1}"
if [ "${SHOW_IDS}" = "YES" ] ; then
  printf "%-23s%-20s%-15s%-10s%-15s%-10s\n" HOST IP AUTOSTART STATUS TYPE ID
else
  printf "%-23s%-20s%-15s%-10s%-15s\n" HOST IP AUTOSTART STATUS TYPE
fi

# Prints a listing of the available jails
echo "-----------------------------------------------------------------------------------------"

cd ${JDIR}

for i in `ls -d .*.meta 2>/dev/null`
do
  HOST="<unknown>"
  AUTO="Disabled" 
  STATUS="<unknown>"

  if [ ! -e "${i}/ip" ] ; then continue ; fi

  # Get the HostName
  if [ -e "${i}/host" ]
  then
    HOST="`cat ${i}/host`"
  fi

  if [ -e "${i}/ip" ]
  then
    IP="`cat ${i}/ip`"
  fi

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

  jIP="`cat ${i}/ip`"

  JAILNAME=`echo ${i}|sed -E 's|^.(.+).meta|\1|'`

  ${PROGDIR}/scripts/backend/checkstatus.sh ${JAILNAME} 2>/dev/null
  if [ "$?" = "0" ]
  then
    STATUS="Running"
  else
    STATUS="Stopped"
  fi

  if [ "${SHOW_IDS}" = "YES" ] ; then
    if [ -e "${i}/ip" ]
    then
      ID="`cat ${i}/id`"
    fi
    printf "%-23s%-20s%-15s%-10s%-15s%-10s\n" ${HOST} ${IP} ${AUTO} ${STATUS} ${TYPE} ${ID}
  else 
    printf "%-23s%-20s%-15s%-10s%-10s\n" ${HOST} ${IP} ${AUTO} ${STATUS} ${TYPE}
  fi 

done

