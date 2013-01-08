#!/bin/sh
# Script to create a new jail based on given flags
#####################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

setup_linux_jail()
{
  echo "Setting up linux jail..."

  mkdir -p ${JMETADIR}
  echo "${HOST}" > ${JMETADIR}/host
  echo "${IP}/${MASK}" > ${JMETADIR}/ip
  if [ "$STARTUP" = "YES" ] ; then
    touch "${JMETADIR}/autostart"
  fi
  touch "${JMETADIR}/jail-linux"

  if [ -n "$LINUXARCHIVE_FILE" ] ; then
    echo "Extracting ${LINUXARCHIVE_FILE}..."
    tar xvf ${LINUXARCHIVE_FILE} -C "${JAILDIR}" 2>/dev/null
    if [ $? -ne 0 ] ; then
       echo "Failed Extracting ${LINUXARCHIVE_FILE}"
       warden delete --confirm ${JAILNAME} 2>/dev/null
       exit 1
    fi
  else
    sh ${LINUX_JAIL_SCRIPT} "${JAILDIR}" "${IP}" "${JMETADIR}"
    if [ $? -ne 0 ] ; then
       echo "Failed running ${LINUX_JAIL_SCRIPT}"
       warden delete --confirm ${JAILNAME} 2>/dev/null
       exit 1
    fi
  fi
  
  # Create the master.passwd
  echo "root::0:0::0:0:Charlie &:/root:/bin/bash" > ${JAILDIR}/etc/master.passwd
  pwd_mkdb -d ${JAILDIR}/tmp -p ${JAILDIR}/etc/master.passwd 2>/dev/null
  mv ${JAILDIR}/tmp/master.passwd ${JAILDIR}/etc/
  mv ${JAILDIR}/tmp/pwd.db ${JAILDIR}/etc/
  mv ${JAILDIR}/tmp/spwd.db ${JAILDIR}/etc/
  rm ${JAILDIR}/tmp/passwd

  # Copy resolv.conf
  cp /etc/resolv.conf ${JAILDIR}/etc/resolv.conf

  # Do some touch-up to make linux happy
  echo '#!/bin/bash
cd /etc
pwconv
grpconv
touch /etc/fstab
touch /etc/mtab
' > ${JAILDIR}/.fixSH
  chmod 755 ${JAILDIR}/.fixSH
  chroot ${JAILDIR} /.fixSH
  rm ${JAILDIR}/.fixSH

  # If we are auto-starting the jail, do it now
  if [ "$STARTUP" = "YES" ] ; then warden start ${JAILNAME} ; fi

  echo "Success! Linux jail created at ${JAILDIR}"
}

# Load our passed values
JAILNAME="${1}"
HOST="${1}"
IP="${2}"
SOURCE="${3}"
PORTS="${4}"
STARTUP="${5}"
JAILTYPE="${6}"
ARCHIVEFILE="${7}"
VERSION="${8}"

case "${JAILTYPE}" in
  portjail) PORTJAIL="YES" ;;
  pluginjail) PLUGINJAIL="YES" ;;
  linuxjail) LINUXJAIL="YES" ;;
  standard) ;;
esac

if [ -z "${VERSION}" ] ; then VERSION=`cat /etc/version`; fi

# Location of the chroot environment
isDirZFS "${JDIR}"
if [ $? -eq 0 ] ; then
  if [ "${PLUGINJAIL}" = "YES" ] ; then
    WORLDCHROOT="${JDIR}/.warden-pj-chroot-${ARCH}"
  else
    WORLDCHROOT="${JDIR}/.warden-chroot-${ARCH}"
  fi
  export WORLDCHROOT
else
  if [ "${PLUGINJAIL}" = "YES" ] ; then
    WORLDCHROOT="${JDIR}/.warden-pj-chroot-${ARCH}.tbz"
  else
    WORLDCHROOT="${JDIR}/.warden-chroot-${ARCH}.tbz"
  fi
  export WORLDCHROOT

fi

get_ip_and_netmask "${IP}"
IP="${JIP}"
MASK="${JMASK}"

# See if we are overriding the default archive file
if [ ! -z "$ARCHIVEFILE" ] ; then
   WORLDCHROOT="$ARCHIVEFILE"
fi

if [ -z "$IP" -o -z "$MASK" -o -z "${HOST}" -o -z "$SOURCE" -o -z "${PORTS}" -o -z "${STARTUP}" ] 
then
  if [ -z "$IP" ] ; then
     echo "ERROR: Missing IP address!"

  elif [ -z "$IP" ] ; then
     echo "ERROR: Missing nemask!"

  elif [ -z "$HOST" ] ; then
     echo "ERROR: Missing hostname!"

  else
     echo "ERROR: Missing required data!"
  fi

  exit 6
fi

JAILDIR="${JDIR}/${JAILNAME}"
set_warden_metadir

if [ -e "${JAILDIR}" ]
then
  echo "ERROR: This Jail directory already exists!"
  exit 5
fi

# Make sure we don't have a host already with this name
for i in `ls -d ${JDIR}/.*.meta 2>/dev/null`
do
  if [ ! -e "${i}/host" ] ; then continue ; fi
  if [ "`cat ${i}/host`" = "$HOST" ] ; then
    echo "ERROR: A jail with this hostname already exists!"
    exit 5
  fi
done

# Check if we need to download the chroot file
if [ "${PLUGINJAIL}" = "YES" ] ; then
  downloadpluginjail "${VERSION}"

elif [ ! -e "${WORLDCHROOT}" -a "${LINUXJAIL}" != "YES" ] ; then
  downloadchroot
fi

# If we are setting up a linux jail, lets do it now
if [ "$LINUXJAIL" = "YES" ] ; then
   isDirZFS "${JDIR}"
   if [ $? -eq 0 ] ; then
     # Create ZFS mount
     tank=`getZFSTank "$JDIR"`
     zfs create -o mountpoint=${JAILDIR} -p ${tank}${JAILDIR}
   else
     mkdir -p "${JAILDIR}"
   fi
   setup_linux_jail
   exit 0
fi

echo "Building new Jail... Please wait..."

isDirZFS "${JDIR}"
if [ $? -eq 0 ] ; then
   # Create ZFS CLONE
   tank=`getZFSTank "$JDIR"`
   zfsp=`getZFSRelativePath "${WORLDCHROOT}"`
   jailp=`getZFSRelativePath "${JAILDIR}"`
   zfs clone ${tank}${zfsp}@clean ${tank}${jailp}
   if [ $? -ne 0 ] ; then exit_err "Failed creating clean ZFS base clone"; fi
else
   # Running on UFS
   mkdir -p "${JAILDIR}"
   echo "Installing world..."
   tar xvf ${WORLDCHROOT} -C "${JAILDIR}" 2>/dev/null
   echo "Done"
fi


mkdir ${JMETADIR}
echo "${HOST}" > ${JMETADIR}/host
echo "${IP}/${MASK}" > ${JMETADIR}/ip

if [ "$SOURCE" = "YES" ]
then
  echo "Installing source..."
  mkdir -p "${JAILDIR}/usr/src"
  if [ ! -e "/usr/src/COPYRIGHT" ] ; then
     echo "No system-sources on host.. You will need to manually download these in the jail."
  else
    tar cvf - -C /usr/src . 2>/dev/null | tar xvf - -C "${JAILDIR}/usr/src" 2>/dev/null
    echo "Done"
  fi
fi

if [ "$PORTS" = "YES" ]
then
  echo "Fetching ports..."
  mkdir -p "${JAILDIR}/usr/ports"
  cat /usr/sbin/portsnap | sed 's|! -t 0|-z '1'|g' | /bin/sh -s "fetch" "extract" "update" "-p" "${JAILDIR}/usr/ports" >/dev/null 2>/dev/null
  if [ $? -eq 0 ] ; then
    echo "Done"
  else
    echo "Failed! Please run \"portsnap fetch extract update\" within the jail."
  fi
fi

# Create an empty fstab
touch "${JAILDIR}/etc/fstab"

# If this isn't a fresh jail, we can skip to not clobber existing setup
if [ -z "$ARCHIVEFILE" ] ; then
  # Setup rc.conf
  echo "portmap_enable=\"NO\"
sshd_enable=\"YES\"
sendmail_enable=\"NO\"
hostname=\"${HOST}\"
devfs_enable=\"YES\"
devfs_system_ruleset=\"devfsrules_common\"" > "${JAILDIR}/etc/rc.conf"

  # Create the host for this device
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

  # Copy resolv.conf
  cp /etc/resolv.conf "${JAILDIR}/etc/resolv.conf"


  # Check if ipv6
  isV6 "${IP}"
  if [ $? -eq 0 ] ; then
    sed -i '' "s|#ListenAddress ::|ListenAddress ${IP}|g" ${JAILDIR}/etc/ssh/sshd_config
  fi

fi # End of ARCHIVEFILE check

if [ "$STARTUP" = "YES" ] ; then
  touch "${JMETADIR}/autostart"
fi

# Check if we need to copy the timezone file
if [ -e "/etc/localtime" ] ; then
   cp /etc/localtime ${JAILDIR}/etc/localtime
fi

# Set the default meta-pkg set
mkdir -p ${JAILDIR}/usr/local/etc >/dev/null 2>/dev/null
echo "PCBSD_METAPKGSET: warden" > ${JAILDIR}/usr/local/etc/pcbsd.conf

# Copy over the pbid scripts
checkpbiscripts "${JAILDIR}"

# Check if making a portjail
if [ "$PORTJAIL" = "YES" ] ; then mkportjail "${JAILDIR}" ; fi

# Check if making a pluginjail
if [ "$PLUGINJAIL" = "YES" ] ; then mkpluginjail "${JAILDIR}" ; fi

# If we are auto-starting the jail, do it now
if [ "$STARTUP" = "YES" ] ; then warden start ${JAILNAME} ; fi

echo "Success!"
echo "Jail created at ${JAILDIR}"

exit 0
