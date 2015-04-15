#!/bin/sh
# Install a package set into a jail
######################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

IFILE="$1"
HOST="${2}"
IP4="${3}"
IP6="${4}"

if [ "${IP4}" != "OFF" ] ; then
  get_ip_and_netmask "${IP4}"
  IP4="${JIP}"
  MASK4="${JMASK}"
fi

if [ "${IP6}" != "OFF" ] ; then
  get_ip_and_netmask "${IP6}"
  IP6="${JIP}"
  MASK6="${JMASK}"
fi

JAILNAME="${HOST}"
JAILDIR="${JDIR}/${JAILNAME}"

if [ -z "${IFILE}" -o ! -e "${IFILE}" ]
then
  warden_error "No jail specified or invalid file!"
  exit 5
fi

if [ -z "${JDIR}" ]
then
  warden_error "JDIR is unset!!!!"
  exit 5
fi

if [ "${IP4}" != "OFF" ]
then
  for i in `ls -d "${JDIR}"/.*.meta 2>/dev/null`
  do
    if [ "`cat "${i}/ipv4" 2>/dev/null`" = "${IP4}/${MASK4}" ] ; then
      warden_error "A Jail exists with IP: ${IP4}"
      exit 5
    fi
  done
fi
if [ "${IP6}" != "OFF" ]
then
  for i in `ls -d "${JDIR}"/.*.meta 2>/dev/null`
  do
    _ipv6="`cat "${i}/ipv6" 2>/dev/null|tr a-z A-Z`"
    _nipv6="`echo ${IP6}|tr a-z A-Z`/${MASK6}"
    if [ "${ipv6}" = "${_nipv6}" ] ; then
      warden_error "A Jail exists with IP: ${IP6}"
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
cd "${WTMP}"
rm -rf tmp.$$ >/dev/null
mkdir tmp.$$
cd tmp.$$

tar xvzf "${IFILE}" >/dev/null 2>/dev/null
if [ "${?}" != "0" ]
then
    warden_error "Extracting header info failed! "
    cd ..
    rm -rf tmp.$$
    exit 5
fi

# Blank our variables and read in the header information
VER=""
OS=""
FILES=""
FIP4=""
FIP6=""
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
  
  # Check for the built in IP4
  echo "$line" | grep -q "IP4:"
  if [ $? -eq 0 ]; then
    FIP4="`echo $line | cut -d ' ' -f 2-10`"
  fi

  # Check for the built in IP6
  echo "$line" | grep -q "IP6:"
  if [ $? -eq 0 ]; then
    FIP6="`echo $line | cut -d ' ' -f 2-10`"
  fi
  
  # Check for the built in HOST
  echo "$line" | grep -q "HOST:"
  if [ $? -eq 0 ]; then
    FHOST="`echo $line | cut -d ' ' -f 2-10`"
  fi

done < "$HEADER"

cd ..

# Make sure this is a file version we understand
if [ "${VER}" != "1.0" ]; then
    warden_error "Specified file is a incompatiable .wdn file!"
    rm -rf tmp.$$ 2>/dev/null
    exit 7
fi

# Check that we are on the same OS platform
if [ "${OS}" != "`uname -r | cut -d '-' -f 1`" ]
then
    warden_print "WARNING: This .wdn file was created on $OS, while this host is `uname -r | cut -d '-' -f 1`"
    warden_print "This jail may not work...Importing anyway..."
fi

if [ "${IP4}" = "OFF" ]
then
  for i in `ls -d "${JDIR}"/.*.meta 2>/dev/null`
  do
    if [ -n "${FIP4}" ] ; then
      if [ "`cat "${i}/ipv4"`" = "${FIP4}" ] ; then
        warden_error "A Jail already exists with IP: $FIP4"
        rm -rf tmp.$$ 2>/dev/null
        exit 7
      fi
    fi
  done
 
  # The user didn't specify a new IPv4 address, so use the built in one
  get_ip_and_netmask "${FIP4}"
  IP4="${JIP}"
  MASK4="${JMASK}"
fi

if [ "${IP6}" = "OFF" ]
then
  for i in `ls -d "${JDIR}"/.*.meta 2>/dev/null`
  do
    if [ -n "${FIP6}" ] ; then

      _ipv6=`cat "${i}/ipv6" 2>/dev/null|tr a-z A-Z`
      _nipv6=`echo ${FIP6}|tr a-z A-Z`
      if [ "${ipv6}" = "${_nipv6}" ] ; then
        warden_error "A Jail already exists with IP: $FIP6"
        rm -rf tmp.$$ 2>/dev/null
        exit 7
      fi
    fi
  done
 
  # The user didn't specify a new IPv6 address, so use the built in one
  get_ip_and_netmask "${FIP6}"
  IP6="${JIP}"
  MASK6="${JMASK}"
fi

SKIP="`awk '/^___WARDEN_START___/ { print NR + 1; exit 0; }' ${IFILE}`"
if [ -n "${IP4}" ] ; then
  warden_print "Importing ${IFILE} with IP: ${IP4}..."
elif [ -n "${IP6}" ] ; then
  warden_print "Importing ${IFILE} with IP: ${IP6}..."
fi

# Make the new directory
JAILDIR="${JDIR}/${HOST}"
isDirZFS "${JDIR}"
if [ $? -eq 0 ] ; then
  # Create ZFS mount
  tank="`getZFSTank "$JDIR"`"
  rp="`getZFSRelativePath "${JAILDIR}"`"
  zfs create -p "${tank}${rp}"
else
  mkdir -p "${JAILDIR}"
fi

# Create the meta-dir
set_warden_metadir
mkdir "${JMETADIR}"

# Copy over extra jail flags
cp tmp.$$/jail-* "${JMETADIR}/" 2>/dev/null

# give new jail an id
set_unique_id "${JDIR}"

# Cleanup tmp meta-dir
rm -rf tmp.$$ 2>/dev/null

# Extract the jail contents
tail +${SKIP} "${IFILE}" | tar xpf - -C "${JAILDIR}" 2>/dev/null

# Make sure we have an IP address saved
if [ -n "${IP4}" ] ; then
  echo "${IP4}/${MASK4}" >"${JMETADIR}/ipv4"
fi
if [ -n "${IP6}" ] ; then
  echo "${IP6}/${MASK6}" >"${JMETADIR}/ipv6"
fi

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
    cat "${JAILDIR}/etc/rc.conf" | grep -v "hostname=" >"${JAILDIR}/.rc.conf"
    echo "hostname=\"${HOST}\"" >>"${JAILDIR}/.rc.conf"
    mv "${JAILDIR}/.rc.conf" "${JAILDIR}/etc/rc.conf"
  fi

# Setup /etc/hosts now
cat<<__EOF__>"${JAILDIR}/etc/hosts"
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
__EOF__

if [ -n "${IP4}" ] ; then
  echo "${IP4}			${HOST}" >> "${JAILDIR}/etc/hosts"
fi
if [ -n "${IP6}" ] ; then
  echo "${IP6}			${HOST}" >> "${JAILDIR}/etc/hosts"
fi

# End Hostname setup
fi

warden_print "Done"
