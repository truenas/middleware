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


# Prints a listing of the available jails
echo "IP			HOST		AUTOSTART	STATUS     TYPE
--------------------------------------------------------------------------------"

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

  # Check if we are autostarting this jail
  if [ -e "${i}/autostart" ] ; then
    AUTO="Enabled"
  fi
 
  # Figure out the type of jail
  if [ -e "${i}/jail-portjail" ] ; then
    TYPE="portjail"
  elif [ -e "${i}/jail-linux" ] ; then
    TYPE="linuxjail"
  else
    TYPE="standard"
  fi

  jIP="`cat ${i}/ip`"

  ${PROGDIR}/scripts/backend/checkstatus.sh ${jIP} 2>/dev/null
  if [ "$?" = "0" ]
  then
    STATUS="Running"
  else
    STATUS="Stopped"
  fi

  # Pad the variables a bit
  IP=`echo "${jIP}                 " | cut -c 1-23`
  AUTO=`echo "${AUTO}              " | cut -c 1-15`
  STATUS=`echo "${STATUS}          " | cut -c 1-10`
  HOST=`echo "${HOST}              " | cut -c 1-15`
  TYPE=`echo "${TYPE}              " | cut -c 1-10`
  

  echo -e "${IP} ${HOST} ${AUTO} ${STATUS} ${TYPE}"
done

