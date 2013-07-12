#!/bin/sh
# Script to create a new jail based on given flags
#####################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

setup_linux_jail()
{
  warden_print "Setting up linux jail..."

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
    warden_print "Extracting ${LINUXARCHIVE_FILE}..."
    tar xvf ${LINUXARCHIVE_FILE} -C "${JAILDIR}" 2>/dev/null
    if [ $? -ne 0 ] ; then
       warden_error "Failed Extracting ${LINUXARCHIVE_FILE}"
       warden delete --confirm ${JAILNAME} 2>/dev/null
       exit 1
    fi
  else
    sh ${LINUX_JAIL_SCRIPT} "${JAILDIR}" "${IP}" "${JMETADIR}"
    if [ $? -ne 0 ] ; then
       warden_error "Failed running ${LINUX_JAIL_SCRIPT}"
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
  if [ "$AUTOSTART" = "YES" ] ; then warden start ${JAILNAME} ; fi

  warden_print "Success! Linux jail created at ${JAILDIR}"
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

# See if we need to create a default template
# If using a ARCHIVEFILE we can skip this step
if [ -z "$TEMPLATE" -a -z "$ARCHIVEFILE" ] ; then
  DEFTEMPLATE="`uname -r | cut -d '-' -f 1-2`-${ARCH}"

  # If on a plugin jail, lets change the nickname
  if [ "${PLUGINJAIL}" = "YES"  ] ; then
    DEFTEMPLATE="${DEFTEMPLATE}-pluginjail"
  fi

  # See if we need to create a new template for this system
  isDirZFS "${JDIR}"
  if [ $? -eq 0 ] ; then
     TDIR="${JDIR}/.warden-template-$DEFTEMPLATE"
  else
     TDIR="${JDIR}/.warden-template-$DEFTEMPLATE.tbz"
  fi

  if [ ! -e "$TDIR" ] ; then
      FLAGS="-arch $ARCH -nick $DEFTEMPLATE"

      uname -r 2>&1 | grep -q "TRUEOS"
      if [ $? -eq 0 ] ; then
         FLAGS="-trueos `uname -r | cut -d '-' -f 1-2` $FLAGS" ; export FLAGS
      else
         FLAGS="-fbsd `uname -r | cut -d '-' -f 1-2` $FLAGS" ; export FLAGS
      fi

      if [ "${PLUGINJAIL}" = "YES" ] ; then
         FLAGS="$FLAGS -pluginjail"
      fi

      ${PROGDIR}/scripts/backend/createtemplate.sh ${FLAGS}
      if [ $? -ne 0 ] ; then
        warden_exit "Failed create default template"
      fi
  fi
  WORLDCHROOT="${TDIR}"

elif [ -z "$ARCHIVEFILE" ] ; then

  # Set WORLDCHROOT to the dir we will clone / file to extract
  WORLDCHROOT="${JDIR}/.warden-template-$TEMPLATE"

  isDirZFS "${JDIR}"
  if [ $? -ne 0 ] ; then
    WORLDCHROOT="${WORLDCHROOT}.tbz"
  fi

else

   # See if we are overriding the default archive file
   WORLDCHROOT="$ARCHIVEFILE"
fi

if [ "${IP4}" != "OFF" ] ; then
  get_ip_and_netmask "${IP4}"
  IP4="${JIP}"
  MASK4="${JMASK}"
  if [ -z "$MASK4" ] ; then MASK4="24"; fi
fi

if [ "${IP6}" != "OFF" ] ; then
  get_ip_and_netmask "${IP6}"
  IP6="${JIP}"
  MASK6="${JMASK}"
  if [ -z "$MASK6" ] ; then MASK6="64"; fi
fi

if [ -z "$HOST" ] ; then
   warden_error "ERROR: Missing hostname!"
   exit 6
fi

JAILDIR="${JDIR}/${JAILNAME}"
set_warden_metadir

if [ -e "${JAILDIR}" ]
then
  warden_error "This Jail directory already exists!"
  exit 5
fi

# Make sure we don't have a host already with this name
for i in `ls -d ${JDIR}/.*.meta 2>/dev/null`
do
  if [ ! -e "${i}/host" ] ; then continue ; fi
  if [ "`cat ${i}/host`" = "$HOST" ] ; then
    warden_error "A jail with this hostname already exists!"
    exit 5
  fi
done

# Get next unique ID
META_ID="$(get_next_id "${JDIR}")"


# If we are setting up a linux jail, lets do it now
if [ "$LINUXJAIL" = "YES" ] ; then
   isDirZFS "${JDIR}"
   if [ $? -eq 0 ] ; then
     # Create ZFS mount
     tank=`getZFSTank "$JDIR"`
     if [ -z "$tank" ] ; then
       warden_exit "Failed getting ZFS dataset for $JDIR..";
     fi
     jailp=`getZFSRelativePath "${JAILDIR}"`
     zfs create -o mountpoint=/${tank}${jailp} -p ${tank}${jailp}
     if [ $? -ne 0 ] ; then warden_exit "Failed creating ZFS dataset"; fi
   else
     mkdir -p "${JAILDIR}"
   fi
   setup_linux_jail

   echo "${META_ID}" > ${JMETADIR}/id
   if [ -d "${PROGDIR}/scripts/hooks" ] ; then
     cp ${PROGDIR}/scripts/hooks/jail-* "${JMETADIR}"
   fi

   exit 0
fi

warden_print "Building new Jail... Please wait..."

isDirZFS "${JDIR}"
if [ $? -eq 0 ] ; then
   # Create ZFS CLONE
   tank=`getZFSTank "$JDIR"`
   zfsp=`getZFSRelativePath "${WORLDCHROOT}"`
   jailp=`getZFSRelativePath "${JAILDIR}"`
   warden_print zfs clone ${tank}${zfsp}@clean ${tank}${jailp}
   zfs clone ${tank}${zfsp}@clean ${tank}${jailp}
   if [ $? -ne 0 ] ; then warden_exit "Failed creating clean ZFS base clone"; fi
else
   # Running on UFS
   mkdir -p "${JAILDIR}"
   warden_print "Installing world..."
   if [ -d "${WORLDCHROOT}" ] ; then
     tar cvf - -C ${WORLDCHROOT} . 2>/dev/null | tar xpvf - -C "${JAILDIR}" 2>/dev/null
   else
     tar xvf ${WORLDCHROOT} -C "${JAILDIR}" 2>/dev/null
   fi

   # If this is a pluginjail on UFS :-( Do things the hard way.
   if [ "${PLUGINJAIL}" = "YES" ] ; then
     bootstrap_pkgng "${pjdir}" "pluginjail"
   fi

   warden_print "Done"
fi

if [ "$VANILLA" != "YES" -a "${PLUGINJAIL}" != "YES" ] ; then
  bootstrap_pkgng "${JAILDIR}"
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
  warden_print "Installing source..."
  mkdir -p "${JAILDIR}/usr/src"
  cd ${JAILDIR}
  SYSVER="$(uname -r)"
  get_file_from_mirrors "/${SYSVER}/${ARCH}/dist/src.txz" "src.txz" "pkg"
  if [ $? -ne 0 ] ; then
    warden_error "Error while downloading the freebsd world."
  else
    warden_print "Extracting sources.. May take a while.."
    tar xvf src.txz -C "${JAILDIR}" 2>/dev/null
    rm src.txz
    warden_print "Done"
  fi
fi

if [ "$PORTS" = "YES" ]
then
  warden_print "Fetching ports..."
  mkdir -p "${JAILDIR}/usr/ports"
  cat /usr/sbin/portsnap | sed 's|! -t 0|-z '1'|g' | /bin/sh -s "fetch" "extract" "update" "-p" "${JAILDIR}/usr/ports" >/dev/null 2>/dev/null
  if [ $? -eq 0 ] ; then
    warden_print "Done"
  else
    warden_error "Failed! Please run \"portsnap fetch extract update\" within the jail."
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
    echo "${IP4}			${HOST}" >> "${JAILDIR}/etc/hosts"
  fi
  if [ "${IP6}" != "OFF" ] ; then
    echo "${IP6}			${HOST}" >> "${JAILDIR}/etc/hosts"
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

# Setup TrueOS PKGNG repo / utilities only if on TRUEOS
if [ "$VANILLA" != "YES" -a -e "${JAILDIR}/etc/rc.delay" ] ; then
  bootstrap_pkgng "${JAILDIR}"
  if [ $? -ne 0 ] ; then
     warden_print "You can manually re-try by running # warden bspkgng ${JAILNAME}"
  fi
fi

# Set the default meta-pkg set
mkdir -p ${JAILDIR}/usr/local/etc >/dev/null 2>/dev/null
echo "PCBSD_METAPKGSET: warden" > ${JAILDIR}/usr/local/etc/pcbsd.conf

# Copy over the pbid scripts
checkpbiscripts "${JAILDIR}"

if [ -d "${PROGDIR}/scripts/hooks" ] ; then
  cp ${PROGDIR}/scripts/hooks/jail-* "${JMETADIR}"
fi

# Check if making a portjail
if [ "$PORTJAIL" = "YES" ] ; then mkportjail "${JAILDIR}" ; fi

# Check if making a pluginjail
if [ "$PLUGINJAIL" = "YES" ] ; then mkpluginjail "${JAILDIR}" ; fi

# If we are auto-starting the jail, do it now
if [ "$AUTOSTART" = "YES" ] ; then warden start ${JAILNAME} ; fi

warden_print "Success!"
warden_print "Jail created at ${JAILDIR}"

if [ "${PLUGINJAIL}" = "YES" ] ; then
  mkdir -p "${JAILDIR}/.plugins"
fi

exit 0
