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

  if [ "${IP4}" != "OFF" ] ; then
    echo "${IP4}/${MASK4}" > ${JMETADIR}/ipv4
  fi
  if [ "${IP6}" != "OFF" ] ; then
    echo "${IP6}/${MASK6}" > ${JMETADIR}/ipv6
  fi

  if [ "$AUTOSTART" = "YES" ] ; then
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

# Everything else is passed via environmental variables

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
  WORLDCHROOT_PLUGINJAIL="${JDIR}/.warden-pj-chroot-${ARCH}"
  WORLDCHROOT_STANDARD="${JDIR}/.warden-chroot-${ARCH}"
else
  WORLDCHROOT_PLUGINJAIL="${JDIR}/.warden-pj-chroot-${ARCH}.tbz"
  WORLDCHROOT_STANDARD="${JDIR}/.warden-chroot-${ARCH}.tbz"
fi
if [ "${PLUGINJAIL}" = "YES" ] ; then
  WORLDCHROOT="${WORLDCHROOT_PLUGINJAIL}"
else
  WORLDCHROOT="${WORLDCHROOT_STANDARD}"
fi
export WORLDCHROOT WORLDCHROOT_PLUGINJAIL WORLDCHROOT_STANDARD

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

# See if we are overriding the default archive file
if [ ! -z "$ARCHIVEFILE" ] ; then
   WORLDCHROOT="$ARCHIVEFILE"
fi

if [ -z "$HOST" ] ; then
   echo "ERROR: Missing hostname!"
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

# Get next unique ID
META_ID=0
for i in `ls -d ${JDIR}/.*.meta 2>/dev/null`
do
  id=`cat ${i}/id`
  if [ "${id}" -gt "${META_ID}" ] ; then
    META_ID="${id}"
  fi
done
: $(( META_ID += 1 ))

# Check if we need to download the chroot file

#
# If this is a pluginjail, we clone a regular freebsd chroot, then we
# bootstrap packageng, install the required packages that a pluginjail
# needs, then snapshot it. Once this is done, creating a pluginjail is
# as easy as doing a zfs clone.
#
if [ "${PLUGINJAIL}" = "YES" -a ! -e "${WORLDCHROOT}" ] ; then
  if [ ! -e "${WORLDCHROOT_STANDARD}" ] ; then
    downloadchroot
  fi

  isDirZFS "${JDIR}"
  if [ $? -eq 0 ] ; then
    tank=`getZFSTank "$JDIR"`
    zfsp=`getZFSRelativePath "${WORLDCHROOT_STANDARD}"`
    clonep="/$(basename ${WORLDCHROOT_PLUGINJAIL})"

    mnt=`getZFSMountpoint ${tank}`
    pjdir="${mnt}${clonep}"

    zfs clone ${tank}${zfsp}@clean ${tank}${clonep}
    if [ $? -ne 0 ] ; then exit_err "Failed creating clean ZFS pluginjail clone"; fi

    cp /etc/resolv.conf ${pjdir}/etc/resolv.conf

    bootstrap_pkgng "${pjdir}" "pluginjail"

    zfs snapshot ${tank}${clonep}@clean
    if [ $? -ne 0 ] ; then exit_err "Failed creating clean ZFS pluginjail snapshot"; fi

  # We're on UFS :-(
  else
    downloadchroot

  fi

elif [ ! -e "${WORLDCHROOT}" -a "${LINUXJAIL}" != "YES" ] ; then
  downloadchroot
fi

# If we are setting up a linux jail, lets do it now
if [ "$LINUXJAIL" = "YES" ] ; then
   isDirZFS "${JDIR}"
   if [ $? -eq 0 ] ; then
     # Create ZFS mount
     tank=`getZFSTank "$JDIR"`
     if [ -z "$tank" ] ; then
       exit_err "Failed getting ZFS dataset for $JDIR..";
     fi
     zfs create -o mountpoint=${JAILDIR} -p ${tank}${JAILDIR}
     if [ $? -ne 0 ] ; then exit_err "Failed creating ZFS dataset"; fi
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
   if [ -d "${WORLDCHROOT}" ] ; then
     tar cvf - -C ${WORLDCHROOT} . 2>/dev/null | tar xpvf - -C "${JAILDIR}" 2>/dev/null
   else
     tar xvf ${WORLDCHROOT} -C "${JAILDIR}" 2>/dev/null
   fi

   # If this is a pluginjail on UFS :-( Do things the hard way.
   if [ "${PLUGINJAIL}" = "YES" ] ; then
     bootstrap_pkgng "${pjdir}" "pluginjail"
   fi

   echo "Done"
fi

mkdir ${JMETADIR}
echo "${HOST}" > ${JMETADIR}/host
if [ "${IP4}" != "OFF" ] ; then
   echo "${IP4}/${MASK4}" > ${JMETADIR}/ipv4
fi
if [ "${IP6}" != "OFF" ] ; then
   echo "${IP6}/${MASK6}" > ${JMETADIR}/ipv6
fi
echo "${META_ID}" > ${JMETADIR}/id

if [ "$SOURCE" = "YES" ]
then
  echo "Installing source..."
  mkdir -p "${JAILDIR}/usr/src"
  cd ${JAILDIR}
  SYSVER="$(uname -r)"
  get_file_from_mirrors "/${SYSVER}/${ARCH}/dist/src.txz" "src.txz"
  if [ $? -ne 0 ] ; then
    echo "Error while downloading the freebsd world."
  else
    echo "Extracting sources.. May take a while.."
    tar xvf src.txz -C "${JAILDIR}" 2>/dev/null
    rm src.txz
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
cat<<__EOF__>"${JAILDIR}/etc/hosts"
# : src/etc/hosts,v 1.16 2003/01/28 21:29:23 dbaker Exp $
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

  if [ "${IP4}" != "OFF" ] ; then
    echo "${IP4}			${HOST}" > "${JAILDIR}/etc/hosts"
  fi
  if [ "${IP6}" != "OFF" ] ; then
    echo "${IP6}			${HOST}" > "${JAILDIR}/etc/hosts"
    sed -i '' "s|#ListenAddress ::|ListenAddress ${IP6}|g" ${JAILDIR}/etc/ssh/sshd_config
  fi

  # Copy resolv.conf
  cp /etc/resolv.conf "${JAILDIR}/etc/resolv.conf"

fi # End of ARCHIVEFILE check

if [ "$AUTOSTART" = "YES" ] ; then
  touch "${JMETADIR}/autostart"
fi

# Allow pinging by default
echo "allow.raw_sockets=true" > ${JMETADIR}/jail-flags

# Check if we need to copy the timezone file
if [ -e "/etc/localtime" ] ; then
   cp /etc/localtime ${JAILDIR}/etc/localtime
fi

# Setup PC-BSD PKGNG repo / utilities
if [ "$VANILLA" != "YES" ] ; then
  bootstrap_pkgng "${JAILDIR}"
  if [ $? -ne 0 ] ; then
     echo "You can manually re-try by running # warden bspkgng ${JAILNAME}"
  fi
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

if [ "${PLUGINJAIL}" = "YES" ] ; then
  mkdir -p "${JAILDIR}/.plugins"
fi

exit 0
