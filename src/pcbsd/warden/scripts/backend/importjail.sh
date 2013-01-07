#!/bin/sh
# Install a package set into a jail
######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

IFILE="$1"
HOST="${2}"
IP="${3}"

get_ip_and_netmask "${IP}"
IP="${JIP}"
MASK="${JMASK}"

JAILNAME="${HOST}"
JAILDIR="${JDIR}/${JAILNAME}"

if [ -z "${IFILE}" -o ! -e "${IFILE}" ]
then
  echo "ERROR: No jail specified or invalid file!"
  exit 5
fi

if [ -z "${JDIR}" ]
then
  echo "ERROR: JDIR is unset!!!!"
  exit 5
fi

if [ "${IP}" != "OFF" ]
then
  for i in `ls -d ${JDIR}/.*.meta 2>/dev/null`
  do
    if [ "`cat ${i}/ip`" = "${IP}" ] ; then
      echo "ERROR: A Jail exists with IP: ${IP}"
      exit 5
    fi
  done
fi
set_warden_metadir

# Lets start importing the jail now
######################################################################


chk=`echo "${IFILE}" | cut -c 1-1`
if [ "$chk" != "/" ]
then
  IFILE="`pwd`/${IFILE}"
fi


# Extract the header info of the file
cd ${WTMP}
rm -rf tmp.$$ >/dev/null
mkdir tmp.$$
cd tmp.$$

tar xvzf ${IFILE} >/dev/null 2>/dev/null
if [ "${?}" != "0" ]
then
    echo "ERROR: Extracting header info failed! "
    cd ..
    rm -rf tmp.$$
    exit 5
fi

# Blank our variables and read in the header information
VER=""
OS=""
FILES=""
FIP=""
FHOST=""

HEADER=`ls *.header`

while read line
do
  #Check for the file version
  echo "$line" | grep -q "Ver:"
  if [ $? -eq 0 ]; then
    VER="`echo $line | cut -d ' ' -f 2-10`"
  fi

  # Check for the OS Platform
  echo "$line" | grep -q "OS:"
  if [ $? -eq 0 ]; then
    OS="`echo $line | cut -d ' ' -f 2-10`"
  fi

  # Check for the File Number 
  echo "$line" | grep -q "Files:"
  if [ $? -eq 0 ]; then
    FILES="`echo $line | cut -d ' ' -f 2-10`"
  fi
  
  # Check for the built in IP
  echo "$line" | grep -q "IP:"
  if [ $? -eq 0 ]; then
    FIP="`echo $line | cut -d ' ' -f 2-10`"
  fi
  
  # Check for the built in HOST
  echo "$line" | grep -q "HOST:"
  if [ $? -eq 0 ]; then
    FHOST="`echo $line | cut -d ' ' -f 2-10`"
  fi

done < $HEADER 

cd ..

# Make sure this is a file version we understand
if [ "${VER}" != "1.0" ]; then
    echo "ERROR: Specified file is a incompatiable .wdn file!"
    rm -rf tmp.$$ 2>/dev/null
    exit 7
fi

# Check that we are on the same OS platform
if [ "${OS}" != "`uname -r | cut -d '-' -f 1`" ]
then
    echo "WARNING: This .wdn file was created on $OS, while this host is `uname -r | cut -d '-' -f 1`"
    echo "This jail may not work...Importing anyway..."
fi

if [ "${IP}" = "OFF" ]
then
  for i in `ls -d ${JDIR}/.*.meta 2>/dev/null`
  do
    if [ "`cat ${i}/ip`" = "${FIP}" ] ; then
      echo "ERROR: A Jail already exists with IP: $FIP"
      rm -rf tmp.$$ 2>/dev/null
      exit 7
    fi
  done
 
  # The user didn't specify a new IP, so use the built in one
  IP="${FIP}"
fi

SKIP="`awk '/^___WARDEN_START___/ { print NR + 1; exit 0; }' ${IFILE}`"
echo "Importing ${IFILE} with IP: ${IP}..."

# Make the new directory
JAILDIR="${JDIR}/${HOST}"
isDirZFS "${JDIR}"
if [ $? -eq 0 ] ; then
  # Create ZFS mount
  tank=`getZFSTank "$JDIR"`
  rp=`getZFSRelativePath "${JAILDIR}"`
  zfs create -p ${tank}${rp}
else
  mkdir -p "${JAILDIR}"
fi

# Create the meta-dir
set_warden_metadir
mkdir ${JMETADIR}

# Copy over extra jail flags
cp tmp.$$/jail-* ${JMETADIR}/ 2>/dev/null

# Cleanup tmp meta-dir
rm -rf tmp.$$ 2>/dev/null

# Extract the jail contents
tail +${SKIP} ${IFILE} | tar xpf - -C "${JAILDIR}" 2>/dev/null

# Make sure we have an IP address saved
echo "${IP}/${MASK}" >"${JMETADIR}/ip"

# Save the jail flags
if [ -n "$JFLAGS" ] ; then
   echo "$JFLAGS" > "${JMETADIR}/jail-flags"
fi

if [ "$HOST" = "OFF" -o -z "${HOST}" ] ; then
  HOST="$FHOST"
fi

# Create the host for this device
if [ "${HOST}" != "OFF" -a ! -z "${HOST}" ]; then
  # Save the details to the .wardenhost file
  echo "${HOST}" >"${JMETADIR}/host"

  # Change the hostname in rc.conf
  if [ -e "${JAILDIR}/etc/rc.conf" ] ; then
    cat "${JAILDIR}/etc/rc.conf" | grep -v "hostname=" >${JAILDIR}/.rc.conf
    echo "hostname=\"${HOST}\"" >>"${JAILDIR}/.rc.conf"
    mv "${JAILDIR}/.rc.conf" "${JAILDIR}/etc/rc.conf"
  fi

# Setup /etc/hosts now
echo "# : src/etc/hosts,v 1.16 2003/01/28 21:29:23 dbaker Exp $
#
# Host Database
#
# This file should contain the addresses and aliases for local hosts that
# share this file.  Replace 'my.domain' below with the domainname of your
# machine.
#
# In the presence of the domain name service or NIS, this file may
# not be consulted at all; see /etc/nsswitch.conf for the resolution order.
#
#
::1                     localhost localhost.localdomain
127.0.0.1               localhost localhost.localdomain ${HOST}
${IP}			${HOST}" > "${JAILDIR}/etc/hosts"

# End Hostname setup
fi

echo "Done"
