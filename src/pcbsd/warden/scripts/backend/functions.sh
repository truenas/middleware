#!/bin/sh

# Functions / variables for warden
######################################################################
# DO NOT EDIT 
PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin
export PATH

# Source local functions
. /usr/local/share/pcbsd/scripts/functions.sh

# Installation directory
PROGDIR="/usr/local/share/warden"

# Jail location
JDIR="$(grep ^JDIR: /usr/local/etc/warden.conf | cut -d' ' -f2)"
export JDIR

CACHEDIR="${JDIR}/.warden-files-cache"
export CACHEDIR

HOME=${JDIR}
export HOME

# Set arch type
REALARCH=`uname -m`
export REALARCH
if [ -z "$ARCH" ] ; then
  ARCH="$REALARCH"
  export ARCH
fi
export UNAME_m="${ARCH}"

# Location of pcbsd.conf file
PCBSD_ETCCONF="/usr/local/etc/pcbsd.conf"

# Network interface to use
NIC="$(grep ^NIC: /usr/local/etc/warden.conf | cut -d' ' -f2)"
export NIC

# Tmp directory
WTMP="$(grep ^WTMP: /usr/local/etc/warden.conf | cut -d' ' -f2)"
export WTMP

# FreeBSD release
FREEBSD_RELEASE="$(grep ^FREEBSD_RELEASE: /usr/local/etc/warden.conf | cut -d' ' -f2)"
if [ -z "${FREEBSD_RELEASE}" ] ; then
  FREEBSD_RELEASE="$(uname -r)"
fi
export UNAME_r="${FREEBSD_RELEASE}"

FREEBSD_MAJOR="$(echo ${FREEBSD_RELEASE}|sed -E 's|^([0-9]+).+|\1|g')"
export FREEBSD_MAJOR

# Temp file for dialog responses
ATMP="/tmp/.wans"
export ATMP

# Warden Version
WARDENVER="1.3"
export WARDENVER

# Dirs to nullfs mount in X jail
NULLFS_MOUNTS="/tmp /media /usr/home"

# Clone directory
CDIR="${JDIR}/clones"

# Tarball extract program
EXTRACT_TARBALL=/usr/local/bin/extract-tarball
: ${EXTRACT_TARBALL_STATUSFILE:="/var/tmp/.extract"}

warden_log() {
  if [ -n "${WARDEN_USESYSLOG}" ] ; then
    logger -t warden $*
  fi
  if [ -n "${WARDEN_LOGFILE}" ] ; then
    echo $* >> "${WARDEN_LOGFILE}"
  fi
};

warden_printf() {
  if [ -n "${WARDEN_USESYSLOG}" ] ; then
    logger -t warden $*
  fi
  if [ -n "${WARDEN_LOGFILE}" ] ; then
    printf $* >> "${WARDEN_LOGFILE}"
  fi
  printf $*
};

warden_cat() {
  if [ -n "${WARDEN_USESYSLOG}" ] ; then
    cat "$*" | logger -t warden
  fi
  if [ -n "${WARDEN_LOGFILE}" ] ; then
    cat "$*" >> "${WARDEN_LOGFILE}"
  fi
  cat "$*"
};

warden_pipe() {
  local val
  while read val; do
    if [ -n "${WARDEN_USESYSLOG}" ] ; then
      logger -t warden "${val}"
    fi
    if [ -n "${WARDEN_LOGFILE}" ] ; then
      echo ${val} >> "${WARDEN_LOGFILE}"
    fi
    echo ${val}
  done
};

warden_print() {
  if [ -n "${WARDEN_USESYSLOG}" ] ; then
    logger -t warden $*
  fi
  if [ -n "${WARDEN_LOGFILE}" ] ; then
    echo $* >> "${WARDEN_LOGFILE}"
  fi
  echo "$*"
};

warden_error() {
  if [ -n "${WARDEN_USESYSLOG}" ] ; then
    logger -t warden "ERROR: $*"
  fi
  if [ -n "${WARDEN_LOGFILE}" ] ; then
    echo "ERROR: $*" >> "${WARDEN_LOGFILE}"
  fi
  echo >&2 "ERROR: $*" 
};

warden_warn() {
  if [ -n "${WARDEN_USESYSLOG}" ] ; then
    logger -t warden "WARN: $*"
  fi
  if [ -n "${WARDEN_LOGFILE}" ] ; then
    echo "WARN: $*" >> "${WARDEN_LOGFILE}"
  fi
  echo >&2 "ERROR: $*" 
};

warden_run() {
  local args

  args="$@"
  if [ -n "${args}" ]
  then
    warden_print "${args}"
    eval ${args}
    return $?
  fi

  return 0
};

warden_exit() {
  warden_error $*
  exit 1
};

### Download the chroot
downloadchroot() {
  local CHROOT="${1}"

  # XXX If this is PCBSD, pbreg get /PC-BSD/Version
  SYSVER="$(echo "$(uname -r)" | cut -f1 -d'-')"
  FBSD_TARBALL="fbsd-release.txz"
  FBSD_TARBALL_CKSUM="${FBSD_TARBALL}.md5"

  # Set the mirror URL, may be overridden by setting MIRRORURL environment variable
  if [ -z "${MIRRORURL}" ]; then
    get_mirror
    MIRRORURL="$VAL"
  fi

  if [ ! -d "${JDIR}" ] ; then mkdir -p "${JDIR}" ; fi
  cd "${JDIR}"

  warden_print "Fetching jail environment. This may take a while..."
  warden_print "Downloading ${MIRRORURL}/${SYSVER}/${ARCH}/netinstall/${FBSD_TARBALL} ..."

  if [ ! -e "$FBSD_TARBALL" ] ; then
     trap "return 1; rm -f ${FBSD_TARBALL}" INT QUIT ABRT KILL TERM EXIT
     get_file "${MIRRORURL}/${SYSVER}/${ARCH}/netinstall/${FBSD_TARBALL}" "$FBSD_TARBALL" 3
     if [ $? -ne 0 ] ; then
       rm -f "${FBSD_TARBALL}"
       warden_exit "Error while downloading the chroot."
     fi
     trap INT QUIT ABRT KILL TERM EXIT
  fi

  if [ ! -e "$FBSD_TARBALL_CKSUM" ] ; then
     trap "return 1; rm -f ${FBSD_TARBALL_CKSUM}" INT QUIT ABRT KILL TERM EXIT
     get_file "${MIRRORURL}/${SYSVER}/${ARCH}/netinstall/${FBSD_TARBALL_CKSUM}" "$FBSD_TARBALL_CKSUM" 3
     if [ $? -ne 0 ] ; then
       rm -f "${FBSD_TARBALL_CKSUM}"
       warden_exit "Error while downloading the chroot checksum."
     fi
     trap INT QUIT ABRT KILL TERM EXIT
  fi

  [ "$(md5 -q "${FBSD_TARBALL}")" != "$(cat "${FBSD_TARBALL_CKSUM}")" ] &&
    warden_error "Error in download data, checksum mismatch. Please try again later."

  # Creating ZFS dataset?
  isDirZFS "${JDIR}"
  if [ $? -eq 0 ] ; then
    trap "rmchroot ${CHROOT}" INT QUIT ABRT KILL TERM EXIT

    local zfsp="`getZFSRelativePath "${CHROOT}"`"

    # Use ZFS base for cloning
    warden_print "Creating ZFS ${CHROOT} dataset..."
    tank="`getZFSTank "${JDIR}"`"
    isDirZFS "${CHROOT}" "1"
    if [ $? -ne 0 ] ; then
       warden_print zfs create -o mountpoint="'/${tank}${zfsp}'" -p "'${tank}${zfsp}'"

       zfs create -o mountpoint="'/${tank}${zfsp}'" -p "'${tank}${zfsp}'"
       if [ $? -ne 0 ] ; then warden_exit "Failed creating ZFS base dataset"; fi
    fi

    warden_print tar xvpf "${FBSD_TARBALL}" -C "${CHROOT}"

    tar xvpf "${FBSD_TARBALL}" -C "${CHROOT}" 2>/dev/null
    if [ $? -ne 0 ] ; then warden_exit "Failed extracting ZFS chroot environment"; fi

    warden_print zfs snapshot "${tank}${zfsp}@clean"

    zfs snapshot "${tank}${zfsp}@clean"
    if [ $? -ne 0 ] ; then warden_exit "Failed creating clean ZFS base snapshot"; fi
    rm "${FBSD_TARBALL}"

    trap INT QUIT ABRT KILL TERM EXIT

  else
    # Save the chroot tarball
    mv "${FBSD_TARBALL}" "${CHROOT}"
  fi
  rm "${FBSD_TARBALL_CKSUM}"
};


rmchroot()
{
  local CHROOT="${1}"

  isDirZFS "${JDIR}"
  if [ $? -eq 0 ] ; then
    local zfsp="`getZFSRelativePath "${CHROOT}"`"
    tank="`getZFSTank "${JDIR}"`"

    warden_print "Destroying dataset ${tank}${zfsp}"
    zfs destroy -fr "${tank}${zfsp}"
    if [ $? -ne 0 ] ; then warden_error "Failed to destroy ZFS base dataset"; fi

    warden_print "Removing ${CHROOT}"
    rm -rf "${CHROOT}" >/dev/null 2>&1
    if [ $? -ne 0 ] ; then warden_error "Failed to remove chroot directory"; fi
  fi
};


### Mount all needed filesystems for the jail
mountjailxfs() {
  for nullfs_mount in ${NULLFS_MOUNTS}; do
    if [ ! -d "${JDIR}/${1}${nullfs_mount}" ] ; then
      mkdir -p "${JDIR}/${1}${nullfs_mount}"
    fi
    if is_symlinked_mountpoint "${nullfs_mount}"; then
      warden_print "${nullfs_mount} has symlink as parent, not mounting"
      continue
    fi

    warden_print "Mounting ${JDIR}/${1}${nullfs_mount}"
    mount_nullfs "${nullfs_mount}" "${JDIR}/${1}${nullfs_mount}"
  done

  # Add support for linprocfs for ports that need linprocfs to build/run
  if [  ! -d "${JDIR}/${1}/compat/linux/proc" ]; then
    mkdir -p "${JDIR}/${1}/compat/linux/proc"
  fi
  if is_symlinked_mountpoint "${JDIR}/${1}/compat/linux/proc"; then
    warden_print "${JDIR}/${1}/compat/linux/proc has symlink as parent, not mounting"
    return
  fi
  warden_print "Enabling linprocfs support."
  mount -t linprocfs linprocfs "${JDIR}/${1}/compat/linux/proc"
}

### Umount all the jail's filesystems
umountjailxfs() {
  status="0"
  # Umount all filesystems that are mounted into the portsjail
  for mountpoint in $(mount | grep "${JDIR}/${1}/" | cut -d" " -f3); do
    if [ "$mountpoint" = "${JDIR}/${1}/dev" ] ; then continue ; fi
    if [ "$mountpoint" = "${JDIR}/${1}/" ] ; then continue ; fi
    if [ "$mountpoint" = "${JDIR}/${1}" ] ; then continue ; fi
    echo "Unmounting $mountpoint"
    umount -f "${mountpoint}"
    if [ $? -ne 0 ] ; then status="1" ; fi
  done
  # Now try to umount /dev
  umount -f "${JDIR}/${1}/dev" 2>/dev/null >/dev/null
  return $status
}

# Check if PBI scripts are loaded in jail
checkpbiscripts() {
  if [ -z "${1}" ] ; then return ; fi
  copypbiscripts "${1}"
}

# Copy PBI scripts to jail
copypbiscripts() {
  if [ -z "${1}" ] ; then return ; fi
  mkdir -p "${1}/usr/local/sbin" >/dev/null 2>/dev/null
  for p in /usr/local/sbin/pbi*
  do
    sed 's|PBI_APPDIR="/var/pbi"|PBI_APPDIR="/usr/pbi"|g' "${p}" > "${1}/${p}"
  done
  chmod 755 "${1}/usr/local/sbin"/pbi*

  # Copy rc.d pbid script
  mkdir -p "${1}/usr/local/etc/rc.d" >/dev/null 2>/dev/null
  cp /usr/local/etc/rc.d/pbid "${1}/usr/local/etc/rc.d/"

  # Copy any PBI manpages
  for man in `find /usr/local/man 2>/dev/null| grep pbi`
  do
    if [ ! -d "${1}`dirname $man`" ] ; then
      mkdir -p "${1}`dirname $man`"
    fi
    cp "${man}" "${1}${man}"
  done

  # Copy libsh
  mkdir -p "${1}/usr/local/share/pcbsd/scripts" >/dev/null 2>/dev/null
  cp /usr/local/share/pcbsd/scripts/functions.sh "${1}/usr/local/share/pcbsd/scripts/functions.sh"

  # Install PC-BSD PBI repo
  out="$(chroot "${1}" /usr/local/sbin/pbi_listrepo|tail +3)"
  if [ -z "${out}" ]  
  then
    cp /usr/local/share/pcbsd/distfiles/pcbsd.rpo "${1}/var/tmp/pcbsd.rpo"
    chroot "${1}" /usr/local/sbin/pbi_addrepo /var/tmp/pcbsd.rpo
    chroot "${1}" chmod 755 /var/db/pbi/keys
    chroot "${1}" /usr/local/sbin/pbi_info >/dev/null 2>&1
  fi

  # Copy dhclient hooks
  cp ${PROGDIR}/scripts/hooks/dhclient-exit-hooks "${1}/etc"
}

checkresolvconf() {
  if [ -z "${1}" ] ; then return ; fi
  if ! [ -s "${1}/etc/resolv.conf" ]; then
    cp /etc/resolv.conf "${1}/etc/resolv.conf" 
  fi 

  grep -iq nameserver "${1}/etc/resolv.conf"
  if [ "$?" != "0" ]; then
    cp /etc/resolv.conf "${1}/etc/resolv.conf" 
  fi
}

mkportjail() {
  if [ -z "${1}" ] ; then return ; fi
  ETCFILES="resolv.conf passwd master.passwd spwd.db pwd.db group localtime"
  for file in ${ETCFILES}; do
    rm "${1}/etc/${file}" >/dev/null 2>&1
    cp "/etc/${file}" "${1}/etc/${file}"
  done
  
  # Need to symlink /home
  chroot "${1}" ln -fs /usr/home /home

  # Make sure we remove our cleartmp rc.d script, causes issues
  [ -e "${1}/etc/rc.d/cleartmp" ] && rm "${1}/etc/rc.d/cleartmp"
  # Flag this type
  echo portjail > "${JMETADIR}/jailtype"
}

mkpluginjail() {
  if [ -z "${1}" ] ; then return ; fi
  ETCFILES="resolv.conf passwd master.passwd spwd.db pwd.db group localtime"
  for file in ${ETCFILES}; do
    rm "${1}/etc/${file}" >/dev/null 2>&1
    cp "/etc/${file}" "${1}/etc/${file}"
  done
  
  # Need to symlink /home
  chroot "${1}" ln -fs /usr/home /home

  # Make sure we remove our cleartmp rc.d script, causes issues
  [ -e "${1}/etc/rc.d/cleartmp" ] && rm "${1}/etc/rc.d/cleartmp"
  # Flag this type
  echo pluginjail > "${JMETADIR}/jailtype"
}

mkZFSSnap() {
  isDirZFS "${1}" "1"
  if [ $? -ne 0 ] ; then warden_error "Not a ZFS volume: ${1}" ; fi
  tank="`getZFSTank "$1"`"
  rp="`getZFSRelativePath "$1"`"
  zdate="`date +%Y-%m-%d-%H-%M-%S`"
  zfs snapshot "$tank${rp}@$zdate"
}

listZFSSnap() {
  isDirZFS "${1}" "1"
  if [ $? -ne 0 ] ; then warden_error "Not a ZFS volume: ${1}" ; fi
  tank="`getZFSTank "$1"`"
  rp="`getZFSRelativePath "$1"`"
  zfs list -t snapshot | grep -w "^${tank}${rp}" | cut -d '@' -f 2 | awk '{print $1}'
}

listZFSClone() {
  isDirZFS "${1}" "1"
  if [ $? -ne 0 ] ; then warden_error "Not a ZFS volume: ${1}" ; fi
  tank="`getZFSTank "$1"`"
  cdir="`getZFSRelativePath "${CDIR}"` "
  warden_print "Clone Directory: ${CDIR}"
  warden_print "-----------------------------------"
  zfs list | grep -w "^${tank}${cdir}/${2}" | awk '{print $5}' | sed "s|${CDIR}/${2}-||g"
}

rmZFSClone() {
  CLONEDIR="${CDIR}/${3}-${2}"
  isDirZFS "${CLONEDIR}" "1"
  if [ $? -ne 0 ] ; then warden_error "Not a ZFS volume: ${CLONEDIR}" ; fi
  tank="`getZFSTank "${CLONEDIR}"`"
  rp="`getZFSRelativePath "${CLONEDIR}"`"
  zfs destroy "${tank}${rp}"
}

rmZFSSnap() {
  isDirZFS "${1}" "1"
  if [ $? -ne 0 ] ; then warden_error "Not a ZFS volume: ${1}" ; fi
  tank="`getZFSTank "$1"`"
  rp="`getZFSRelativePath "$1"`"
  zfs destroy "$tank${rp}@$2"
}

revertZFSSnap() {
  isDirZFS "${1}" "1"
  if [ $? -ne 0 ] ; then warden_error "Not a ZFS volume: ${1}" ; fi
  tank="`getZFSTank "$1"`"
  rp="`getZFSRelativePath "$1"`"

  # Make sure this is a valid snapshot
  zfs list -t snapshot | grep -w "^${tank}${rp}" | cut -d '@' -f 2 | awk '{print $1}' | grep -q ${2}
  if [ $? -ne 0 ] ; then warden_error "Invalid ZFS snapshot!" ; fi

  # Check if the jail is running first
  ${PROGDIR}/scripts/backend/checkstatus.sh "${3}"
  if [ "$?" = "0" ]; then
    restartJail="YES"
    # Make sure the jail is stopped
    ${PROGDIR}/scripts/backend/stopjail.sh "${3}"
    ${PROGDIR}/scripts/backend/checkstatus.sh "${3}"
    if [ "$?" = "0" ]; then
      warden_error "Could not stop jail... Halting..."
    fi
  fi

  # Rollback the snapshot
  zfs rollback -R -f "${tank}${rp}@$2"

  # If it was started, restart the jail now
  if [ "$restartJail" = "YES" ]; then
    ${PROGDIR}/scripts/backend/startjail.sh "${3}"
  fi
  
}

cloneZFSSnap() {
  isDirZFS "${1}" "1"
  if [ $? -ne 0 ] ; then warden_error "Not a ZFS volume: ${1}" ; fi
  tank="`getZFSTank "$1"`"
  rp="`getZFSRelativePath "$1"`"
  cdir="`getZFSRelativePath "${CDIR}"`"

  # Make sure this is a valid snapshot
  zfs list -t snapshot | grep -w "^${tank}${rp}" | cut -d '@' -f 2 | awk '{print $1}' | grep -q "${2}"
  if [ $? -ne 0 ] ; then warden_error "Invalid ZFS snapshot!" ; fi

  if [ -d "${CDIR}/${3}-${2}" ] ; then
     warden_error "This snapshot is already cloned and mounted at: ${CDIR}/${3}-${2}"
  fi

  # Clone the snapshot
  zfs clone -p "${tank}${rp}@$2 ${tank}${cdir}/${3}-${2}"

  warden_print "Snapshot cloned and mounted to: ${CDIR}/${3}-${2}"
}

set_warden_metadir()
{
   JMETADIR="${JDIR}/.${JAILNAME}.meta"
   export JMETADIR
}

get_ip_and_netmask()
{
   JIP=`echo "${1}" | cut -f1 -d'/'`
   JMASK=`echo "${1}" | cut -f2 -d'/' -s`
}

get_interface_addresses()
{
   local iface="${1}"
   local jid="${2}"
   local jexec="jexec ${jid}"
   
   if [ -z "${jid}" ]
   then
      jexec="" 
   fi

   eval ${jexec} ifconfig "${iface}" | grep -w inet | awk '{ print $2 }'
}

get_interface_ipv4_addresses()
{
   local iface="${1}"
   local jid="${2}"
   local jexec="jexec ${jid}"

   if [ -z "${jid}" ]
   then
      jexec="" 
   fi

   eval ${jexec} ifconfig "${iface}" | grep -w inet | awk '{ print $2 }'
}

get_interface_ipv6_addresses()
{
   local iface="${1}"
   local jid="${2}"
   local jexec="jexec ${jid}"
   local addrs

   if [ -z "${jid}" ]
   then 
      jexec=""
   fi

   addrs="$(eval ${jexec} ifconfig "${iface}" | \
      grep -w inet6 | grep -v scope | awk '{ print $2 }')"
   for addr in ${addrs} ; do
      echo "${addr}" | cut -f1 -d'%'
   done
}

get_interface_address()
{
   local iface="${1}"
   local jid="${2}"
   local jexec="jexec ${jid}"

   if [ -z "${jid}" ]
   then
      jexec=""
   fi

   eval ${jexec} ifconfig "${iface}" | grep -w inet | \
      head -1 | awk '{ print $2 }'
}

get_interface_ipv4_address()
{
   local iface="${1}"
   local jid="${2}"
   local jexec="jexec ${jid}"

   if [ -z "${jid}" ]
   then
      jexec=""
   fi

   eval ${jexec} ifconfig "${iface}" | grep -w inet | \
      head -1 | awk '{ print $2 }'
}

get_interface_ipv6_address()
{
   local iface="${1}"
   local jid="${2}"
   local jexec="jexec ${jid}"

   if [ -z "${jid}" ]
   then
      jexec=""
   fi

   eval ${jexec} ifconfig "${iface}" | grep -w inet6 | \
       grep -v scope | head -1 | awk '{ print $2 }' | cut -f1 -d'%'
}

get_interface_aliases()
{
   local iface="${1}"
   local jid="${2}"
   local jexec="jexec ${jid}"
   local count

   if [ -z "${jid}" ]
   then
      jexec=""
   fi

   count="$(eval ${jexec} ifconfig "${iface}" | grep -w inet | wc -l)"
   count="$(echo "${count} - 1" | bc)"
   if [ "${count}" -lt "0" ]
   then
      return
   fi

   eval ${jexec} ifconfig "${iface}" | \
      grep -w inet | tail -${count} | awk '{ print $2 }'
}

get_interface_ipv4_aliases()
{
   local iface="${1}"
   local jid="${2}"
   local jexec="jexec ${jid}"
   local count

   if [ -z "${jid}" ]
   then
      jexec=""
   fi

   count="$(eval ${jexec} ifconfig "${iface}" | grep -w inet | wc -l)"
   count="$(echo "${count} - 1" | bc)"
   if [ "${count}" -lt "0" ]
   then
      return
   fi

   eval ${jexec} ifconfig "${iface}" | \
      grep -w inet | tail -${count} | awk '{ print $2 }'
}

get_interface_ipv6_aliases()
{
   local iface="${1}"
   local jid="${2}"
   local jexec="jexec ${jid}"
   local count

   if [ -z "${jid}" ]
   then
      jexec=""
   fi

   count="$(eval ${jexec} ifconfig "${iface}" | grep -w inet | wc -l)"
   count="$(echo "${count} - 1" | bc)"
   if [ "${count}" -lt "0" ]
   then
      return
   fi

   eval ${jexec} ifconfig "${iface}" | \
      grep -w inet6 | grep -v scope | tail -${count} | awk '{ print $2 }'
}

get_default_ipv4_route()
{
   local jid="${1}"
   local jexec="jexec ${jid}"

   if [ -z "${jid}" ]
   then
      jexec=""
   fi

   eval ${jexec} route -nv show default 2>/dev/null | \
      grep -w gateway | awk '{ print $2 }' | cut -f1 -d'%'
}

get_default_ipv6_route()
{
   local jid="${1}"
   local jexec="jexec ${jid}"

   if [ -z "${jid}" ]
   then
      jexec=""
   fi

   eval ${jexec} route -nv show -inet6 default 2>/dev/null | \
      grep -w gateway | awk '{ print $2 }' | cut -f1 -d'%'
}

get_default_interface()
{
   local jid="${1}"
   local jexec="jexec ${jid}"

   if [ -z "${jid}" ]
   then
      jexec=""
   fi

   eval ${jexec} route -nv show default 2>/dev/null | \
      grep -w interface | awk '{ print $2 }'
}

get_default_ipv4_interface()
{
   local jid="${1}"
   local jexec="jexec ${jid}"

   if [ -z "${jid}" ]
   then
      jexec=""
   fi

   eval ${jexec} route -nv show default 2>/dev/null | \
      grep -w interface | awk '{ print $2 }'
}

get_default_ipv6_interface()
{
   local jid="${1}"
   local jexec="jexec ${jid}"

   if [ -z "${jid}" ]
   then
      jexec=""
   fi

   eval ${jexec} route -nv show -inet6 default 2>/dev/null | \
      grep -w interface | awk '{ print $2 }'
}

get_bridge_interfaces()
{
   ifconfig -a | grep -E '^bridge[0-9]+' | cut -f1 -d:
}

get_bridge_members()
{
   ifconfig "${1}" | grep -w member | awk '{ print $2 }'
}

get_bridge_interface_by_ipv4_network()
{
   local network="${1}"
   local bridges="$(get_bridge_interfaces)"

   if [ -z "${network}" ]
   then
      return 1
   fi

   for _bridge in ${bridges}
   do
      local ips="$(get_interface_ipv4_aliases "${_bridge}")"
      for _ip in ${ips}
      do
         if in_ipv4_network "${_ip}" "${network}"
         then
            echo "${_bridge}"
            return 0
         fi
      done
   done

   return 1
}

get_bridge_interface_by_ipv6_network()
{
   local network="${1}"
   local bridges="$(get_bridge_interfaces)"

   if [ -z "${network}" ]
   then
      return 1
   fi

   for _bridge in ${bridges}
   do
      local ips="$(get_interface_ipv6_aliases "${_bridge}")"
      for _ip in ${ips}
      do
         if in_ipv6_network "${_ip}" "${network}"
         then
            echo "${_bridge}"
            return 0
         fi
      done
   done

   return 1
}

is_bridge_member()
{
   local _bridge="${1}"
   local _iface="${2}"

   for _member in `get_bridge_members ${_bridge}`
   do
      if [ "${_member}" = "${_iface}" ] ; then
         return 0
      fi
   done

   return 1
}

jail_interfaces_down()
{
   local _jid="${1}"
   local _bridgeif
   local _epaira
   local _epairb
   local _addresses

   _epairb=`jexec ${_jid} ifconfig -a | grep '^epair' | cut -f1 -d:`
   if [ -n "${_epairb}" ] ; then
      _epaira=`echo ${_epairb} | sed -E 's|b$|a|'`
      _bridgeif=

      for _bridge in `ifconfig -a | grep -E '^bridge[0-9]+' | cut -f1 -d:`
      do
         for _member in `ifconfig ${_bridge} | grep member | awk '{ print $2 }'`
         do
            if [ "${_member}" = "${_epaira}" ] ; then
               _bridgeif="${_bridge}"
                break
            fi
         done
         if [ -n "${_bridgeif}" ] ; then
            break
         fi
      done

      _addresses="$(get_interface_ipv4_addresses ${_epairb} ${_jid})"
      for _ip4 in ${_addresses}
      do
         rules="$(ipfw list|egrep "from ${_ip4} to any out xmit"|awk '{ print $1 }')"
         if [ -n "${rules}" ] 
         then
            for rule in ${rules}
            do
               ipfw delete "${rule}"
            done
         fi
	 /usr/sbin/arp -d "${_ip4}"
      done

      _addresses="$(get_interface_ipv6_addresses ${_epairb} ${_jid})"
      for _ip6 in ${_addresses}
      do
         rules="$(ipfw list|egrep "from ${_ip6} to any out xmit"|awk '{ print $1 }')"
         if [ -n "${rules}" ] 
         then
            for rule in ${rules}
            do
               ipfw delete "${rule}"
            done
         fi
      done

      jexec ${_jid} ifconfig ${_epairb} down
      ifconfig ${_epaira} down
      ifconfig ${_epaira} destroy
      _count=`ifconfig ${_bridgeif} | grep member | awk '{ print $2 }' | wc -l`
      if [ "${_count}" -le "1" ] ; then
         local _member
         local _instances

         _member="`ifconfig "${_bridgeif}"|grep member|awk '{ print $2 }'`"

         _instances="`get_ipfw_nat_instance ${_member}`"
         if [ -n "${_instances}" ]
         then
            for _instance in ${_instances}  
            do
               ipfw nat "${_instance}" delete
            done
         fi

         _addresses="$(get_interface_ipv4_addresses ${_member})"
         for _ip4 in ${_addresses}
         do
            rules="$(ipfw list|egrep "from any to "${_ip4}" in recv"|awk '{ print $1 }')"
            if [ -n "${rules}" ] 
            then
               for rule in ${rules}
               do
                  ipfw delete "${rule}"
               done
            fi
         done

         _addresses="$(get_interface_ipv6_addresses ${_member})"
         for _ip6 in ${_addresses}
         do
            rules="$(ipfw list|egrep "from any to "${_ip6}" in recv"|awk '{ print $1 }')"
            if [ -n "${rules}" ] 
            then
               for rule in ${rules}
               do
                  ipfw delete "${rule}"
               done
            fi
         done

         ifconfig "${_bridgeif}" destroy
      fi
   fi
}

enable_cron()
{
   cronscript="${PROGDIR}/scripts/backend/cronsnap.sh"
   grep -q "${cronscript}" /etc/crontab
   if [ $? -eq 0 ] ; then return 0 ; fi
   echo "2     *        *       *       *        root    ${cronscript}" >> /etc/crontab
   # Restart cron
   /etc/rc.d/cron restart >/dev/null 2>/dev/null
}

fix_old_meta()
{
   for i in `ls -d "${JDIR}"/.*.meta 2>/dev/null`
   do
      if [ -e "${i}/xjail" ] ; then
         touch "${i}/jail-portjail" 2>/dev/null
      fi
      if [ -e "${i}/linuxjail" ] ; then
         touch "${i}/jail-linux" 2>/dev/null
      fi
   done
}

is_ipv4()
{
   local addr="${1}"
   local res=1

   local ipv4="$(/usr/local/bin/sipcalc "${addr}"|head -1|cut -f2 -d'['|awk '{ print $1 }')"
   if [ "${ipv4}" = "ipv4" ]
   then
      res=0
   fi

   return ${res}
}

is_ipv6()
{
   local addr="${1}"
   local res=1

   local ipv6="$(/usr/local/bin/sipcalc "${addr}"|head -1|cut -f2 -d'['|awk '{ print $1 }')"
   if [ "${ipv6}" = "ipv6" ]
   then
      res=0
   fi

   return ${res}
}

in_ipv4_network()
{
   local addr="${1}"
   local network="${2}"
   local res=1

   local start="$(/usr/local/bin/sipcalc "${network}"|awk '/^Usable/ { print $4 }')"
   local end="$(/usr/local/bin/sipcalc "${network}"|awk '/^Usable/ { print $6 }')"

   local iaddr="$(/usr/local/bin/sipcalc "${addr}"|awk '/(decimal)/ { print $5 }')"
   local istart="$(/usr/local/bin/sipcalc "${start}"|awk '/(decimal)/ { print $5 }')"
   local iend="$(/usr/local/bin/sipcalc "${end}"|awk '/(decimal)/ { print $5 }')"

   if [ "${iaddr}" -ge "${istart}" -a "${iaddr}" -le "${iend}" ]
   then
      res=0
   fi

   return ${res}
}

ipv6_to_binary()
{
   echo ${1}|awk '{
      split($1, octets, ":");
      olen = length(octets);
		
      bnum = "";
      for (i = 1;i <= olen;i++) {
         tbnum = "";
         dnum = int(sprintf("0x%s", octets[i]));
         for (;;) {
            rem = int(dnum % 2);
            if (rem == 0) 
               tbnum = sprintf("0%s", tbnum);
            else		
               tbnum = sprintf("1%s", tbnum);
            dnum /= 2;
            if (dnum < 1)
               break;
         }
         bnum = sprintf("%s%016s", bnum, tbnum);
      }
      printf("%s", bnum);
   }'
}

in_ipv6_network()
{
   local addr="${1}"
   local network="${2}"
   local mask="$(echo "${network}"|cut -f2 -d'/' -s)"
   local res=1

   local addr="$(/usr/local/bin/sipcalc "${addr}"|awk \
      '/^Expanded/ { print $4}')"
   local start="$(/usr/local/bin/sipcalc "${network}"|egrep \
      '^Network range'|awk '{ print $4 }')"

   local baddr="$(ipv6_to_binary "${addr}")"
   local bstart="$(ipv6_to_binary "${start}")"

   local baddrnet="$(echo "${baddr}"|awk -v mask="${mask}" \
      '{ s = substr($0, 1, mask); printf("%s", s); }')"
   local bstartnet="$(echo "${bstart}"|awk -v mask="${mask}" \
      '{ s = substr($0, 1, mask); printf("%s", s); }')"

   if [ "${baddrnet}" = "${bstartnet}" ]
   then
      res=0
   fi

   return ${res}
}

install_pc_extractoverlay()
{
  if [ -z "${1}" ] ; then
    return 1 
  fi 

  mkdir -p "${1}/usr/local/bin"
  mkdir -p "${1}/usr/local/share/pcbsd/conf"
  mkdir -p "${1}/usr/local/share/pcbsd/distfiles"

  cp /usr/local/bin/pc-extractoverlay "${1}/usr/local/bin/"
  chmod 755 "${1}/usr/local/bin/pc-extractoverlay"

  cp /usr/local/share/pcbsd/conf/server-excludes \
    "${1}/usr/local/share/pcbsd/conf"
  cp /usr/local/share/pcbsd/distfiles/server-overlay.txz \
    "${1}/usr/local/share/pcbsd/distfiles"

  return 0
}

CR()
{
    local res
    local jaildir="${1}"
    shift

    mount -t devfs none "${jaildir}/dev"
    devfs -m "${jaildir}/dev" rule -s 4 applyset

    chroot "${jaildir}" /bin/sh -exc "$@" | warden_pipe
    umount "${jaildir}/dev"
}

get_dependencies_port_list()
{
  local jaildir="${1}"
  local pkgdir="${2}"
  local list="${3}"
  local deplist
  local ulist

  if [ ! -d "${jaildir}" -o ! -d "${pkgdir}" -o ! -f "${list}" ] ; then
    return 1
  fi

  deplist="$(mktemp /tmp/.depXXXXXX)"
  for p in $(cat "${list}") ; do
    ${CR} "pkg rquery '%do' ${p}" >> "${deplist}" 2>/dev/null
    echo ${p} >> "${deplist}"
  done  

  ulist="$(mktemp /tmp/.ulXXXXXX)"
  cat "${deplist}"|uniq > "${ulist}"
  rm -f "${deplist}"

  cat "${ulist}"
  rm -f "${ulist}"

  return 0
}

get_package_install_list()
{
  local jaildir="${1}"
  local pkgdir="${2}"
  local list="${3}"
  local pkginfo
  local pkgs
  local ilist

  if [ ! -d "${jaildir}" -o ! -d "${pkgdir}" -o ! -f "${list}" ] ; then
    return 1
  fi

  pkginfo="$(mktemp /tmp/.piXXXXXX)" 
  ilist="$(mktemp /tmp/.ilXXXXXX)" 

  ${CR} "mkdir -p /var/tmp/pkgs"
  mount_nullfs "${pkgdir}" "${jaildir}/var/tmp/pkgs"
  pkgs="$(${CR} "ls /var/tmp/pkgs")"
  for p in ${pkgs} ; do
    ${CR} "pkg info -oF /var/tmp/pkgs/${p}" >> "${pkginfo}" 2>/dev/null
  done
  umount "${jaildir}/var/tmp/pkgs"

  exec 3<&0
  exec 0<"${pkginfo}"
  while read -r pi ; do
    local pkg="$(echo "${pi}" | cut -f1 -d' ' -d':' | awk '{ print $1 }')"
    local port="$(echo "${pi}" | cut -f2 -d' ' | awk '{ print $1 }')"

    grep -qw "${port}" "${list}" 2>/dev/null
    if [ "$?" = "0" ] ; then
      echo "${pkg}.txz" >> "${ilist}"
    fi

  done
  exec 0<&3

  rm -f "${pkginfo}"

  cat "${ilist}"
  rm -f "${ilist}"

  return 0
}

install_packages_by_list()
{
  local jaildir="${1}"
  local pkgdir="${2}"
  local list="${3}"

  if [ ! -d "${jaildir}" -o ! -d "${pkgdir}" -o ! -f "${list}" ] ; then
    return 1
  fi

  ${CR} "mkdir -p /var/tmp/pkgs"
  mount_nullfs "${pkgdir}" "${jaildir}/var/tmp/pkgs"
  for p in $(cat "${list}") ; do
    if [ -f "${jaildir}/var/tmp/pkgs/${p}" ] ; then
      ${CR} "pkg add /var/tmp/pkgs/${p}"
    fi
    show_progress
  done
  umount "${jaildir}/var/tmp/pkgs"

  return 0
}

create_jail_pkgconf()
{
  local jaildir="${1}"
  local pkgsite="${2}"
  local arch="${3}"

  if [ "${arch}" = "amd64" ]
  then
    arch="64"
  else
    arch="32"
  fi  

  : ${pkgsite:="http://pkg.FreeBSD.org/freebsd:${FREEBSD_MAJOR}:x86:${arch}/latest"}

  if [ ! -d "${jaildir}" -o -z "${pkgsite}" ] ; then 
    return 1
  fi

  rm -f "${jaildir}/usr/local/etc/pkg.conf"
  mkdir -p "${jaildir}/usr/local/etc/pkg/repos"

  cat<<__EOF__>"${jaildir}/usr/local/etc/pkg/repos/FreeBSD.conf"
FreeBSD: {
  url: "pkg+${pkgsite}",
  mirror_type: "srv",
  enabled: yes
}
__EOF__

  return 0
}

get_package()
{
  local jaildir="${1}"
  local pkgdir="${2}"
  local rpath="${3}"
  local pkg="${4}"

  if [ ! -d "${jaildir}" -o ! -d "${pkgdir}" -o -z "${pkg}" ] ; then
    return 1
  fi
  warden_print "Downloading ${pkg}"

  if [ ! -f "${pkgdir}/${pkg}" ] ; then
    get_file_from_mirrors "${rpath}/All/${pkg}" \
      "${jaildir}/var/tmp/pkgs/${pkg}" "pkg"
  fi

  return 0
}

get_packages_by_port_list()
{
  local jaildir="${1}"
  local pkgdir="${2}"
  local rpath="${3}"
  local list="${4}"

  if [ ! -d "${jaildir}" -o ! -d "${pkgdir}" -o ! -f "${list}" ] ; then
    return 1
  fi

  local pkgs="$(${CR} "pkg rquery '%n-%v.txz\n%dn-%dv.txz' $(cat "${list}" | tr -s '\n' ' ')")"
  pkgs=$(echo ${pkgs} | tr -s " " "\n" | sort | uniq)

  ${CR} "mkdir -p /var/tmp/pkgs"
  mount_nullfs "${pkgdir}" "${jaildir}/var/tmp/pkgs"
  for p in ${pkgs} ; do 
    get_package "${jaildir}" "${pkgdir}" "${rpath}" "${p}" 
  done
  umount "${jaildir}/var/tmp/pkgs"

  return 0
}

show_progress()
{
  local percent=0

  if [ -z "${CURRENT_INSTALL_FILE}" ] ; then
    CURRENT_INSTALL_FILE=1
    export CURRENT_INSTALL_FILE
  fi

  if [ -z "${TOTAL_INSTALL_FILES}" ] ; then
    TOTAL_INSTALL_FILES=0
    export TOTAL_INSTALL_FILES
  fi

  if [ "${TOTAL_INSTALL_FILES}" -gt "0" ] ; then
    percent=`echo "scale=2;(${CURRENT_INSTALL_FILE}/${TOTAL_INSTALL_FILES})*100"|bc|cut -f1 -d.`
    if [ "${CURRENT_INSTALL_FILE}" -ge "${TOTAL_INSTALL_FILES}" ] ; then
      percent=100
    fi

    : $(( CURRENT_INSTALL_FILE += 1 ))
    export CURRENT_INSTALL_FILE

    warden_print "===== ${percent}% ====="
  fi
}

bootstrap_pkgng()
{
  local jaildir="${1}"
  local jailtype="${2}"
  if [ -z "${jailtype}" ] ; then
    jailtype="standard"
  fi

  CR="CR "${jaildir}""
  export CR

  local arch="${ARCH}"
  local release="$(uname -r | cut -d '-' -f 1-2)"

  local mirrorfile="/usr/local/share/pcbsd/conf/pcbsd-mirrors"
  local mirror
  local rpath

  if [ "${arch}" != "i386" ] ; then
    mirror="http://pkg.cdn.pcbsd.org"
    rpath="/freenas/${release}/${arch}"
  else
    mirror="http://mirror.exonetric.net/pub/pkgng/freebsd:9:x86:32/latest"
    mirrorfile="/usr/local/share/pcbsd/conf/pkg-mirror"
    rpath=""

    local tmp="$(mktemp /tmp/.mirXXXXXX)"
    echo "${mirror}" > "${tmp}"

    #
    # XXX ugly! but for now, necessary! XXX
    #

    mount -uw /
    mv "${tmp}" "${mirrorfile}-i386"
    mount -ur /

    chmod 644 "${mirrorfile}"
  fi

  local pkgdir="${CACHEDIR}/packages/${release}/${arch}"

  cd "${jaildir}"
  warden_print "Boot-strapping pkgng"

  mkdir -p "${jaildir}/usr/local/etc"
  mkdir -p "${jaildir}/usr/local/tmp"
  pubcert="/usr/local/etc/pkg-pubkey.cert"

  cp "${pubcert}" "${jaildir}/usr/local/etc"
  install_pc_extractoverlay "${jaildir}"

  create_jail_pkgconf "${jaildir}" "${mirror}${rpath##/packages}" "${arch}"

  if [ ! -d "${pkgdir}" ] ; then
    mkdir -p "${pkgdir}"
  fi

  if [ -f "${pkgdir}/pkg.txz" ] ; then
    cp "${pkgdir}/pkg.txz" "${jaildir}/usr/local/tmp"
  else
    get_file_from_mirrors "${rpath}/Latest/pkg.txz" \
      "${pkgdir}/pkg.txz" "pkg"
    cp "${pkgdir}/pkg.txz" "${jaildir}/usr/local/tmp"
  fi
  local pres=$? 

  if [ -f "${pkgdir}/repo.txz" ] ; then
    cp "${pkgdir}/repo.txz" "${jaildir}/usr/local/tmp"
  else
    get_file_from_mirrors "${rpath}/repo.txz" \
      "${pkgdir}/repo.txz" "pkg"
    cp "${pkgdir}/repo.txz" "${jaildir}/usr/local/tmp"
  fi
  local rres=$? 

  if [ "${pres}" = "0" -a "${rres}" = "0" ] ; then
    local pclist="${PROGDIR}/pcbsd-utils-packages"
    local pjlist="${PROGDIR}/pluginjail-packages"

    ${CR} "tar -xvf /usr/local/tmp/pkg.txz -C / --exclude +MANIFEST --exclude +MTREE_DIRS"
    ${CR} "pkg add /usr/local/tmp/pkg.txz"

    if [ -f "${pkgdir}/repo.sqlite" ] ; then
      cp "${pkgdir}/repo.sqlite" "${jaildir}/var/db/pkg"
    else
      ${CR} "tar -xvf /usr/local/tmp/repo.txz -C /var/db/pkg/"
    fi

    if [ -f "${pkgdir}/local.sqlite" ] ; then
      cp "${pkgdir}/local.sqlite" "${jaildir}/var/db/pkg"
    fi

    if [ -f "${pkgdir}/repo-packagesite.sqlite" ] ; then
      cp "${pkgdir}/repo-packagesite.sqlite" "${jaildir}/var/db/pkg"
    fi

    chroot "${jaildir}" /bin/sh -exc "pkg rquery '%n' pkg" 2>/dev/null
    if [ "$?" != "0" ] ; then
      ${CR} "pkg update"   
    fi

    get_packages_by_port_list "${jaildir}" \
      "${pkgdir}" "${rpath}" "${pclist}"

    if [ "${jailtype}" = "pluginjail" ] ; then
      get_packages_by_port_list "${jaildir}" "${pkgdir}" \
        "${rpath}" "${pjlist}"
    fi

    local ilist="$(mktemp /tmp/.ilXXXXXX)"
    get_package_install_list "${jaildir}" \
      "${pkgdir}" "${pclist}" > "${ilist}"
    install_packages_by_list "${jaildir}" "${pkgdir}" "${ilist}"

    if [ "${jailtype}" = "pluginjail" ] ; then
      get_package_install_list "${jaildir}" \
        "${pkgdir}" "${pjlist}"  > "${ilist}"
      install_packages_by_list "${jaildir}" "${pkgdir}" "${ilist}"
    fi

    rm -f "${ilist}"

    ${CR} "pc-extractoverlay server --sysinit"
    create_jail_pkgconf "${jaildir}" "${mirror}/${rpath##/packages}" "${arch}"

    return 0
  fi

  warden_error "Failed boot-strapping PKGNG, most likely cause is internet connection failure."
  return 1
}

ipv4_configured()
{
   local iface="${1}"
   local jid="${2}"
   local jexec=

   if [ -n "${jid}" ] ; then
      jexec="jexec ${jid}"
   fi

   eval ${jexec} ifconfig "${iface}" | grep -qw inet 2>/dev/null
   return $?
}

ipv4_address_configured()
{
   local iface="${1}"
   local addr="${2}"
   local jid="${3}"
   local jexec= 

   addr="$(echo ${addr}|cut -f1 -d'/')"

   if [ -n "${jid}" ] ; then
      jexec="jexec ${jid}"
   fi

   eval ${jexec} ifconfig "${iface}" | \
      grep -w inet | \
      awk '{ print $2 }' | \
      grep -Ew "^${addr}" >/dev/null 2>&1
   return $?
}

ipv6_configured()
{
   local iface="${1}"
   local jid="${2}"
   local jexec=

   if [ -n "${jid}" ] ; then
      jexec="jexec ${jid}"
   fi

   eval ${jexec} ifconfig "${iface}" | \
       grep -qw inet6 | grep -v scope 2>/dev/null
   return $?
}

ipv6_address_configured()
{
   local iface="${1}"
   local addr="${2}"
   local jid="${3}"
   local jexec= 

   addr="$(echo ${addr}|cut -f1 -d'/')"

   if [ -n "${jid}" ] ; then
      jexec="jexec ${jid}"
   fi

   eval ${jexec} ifconfig "${iface}" | \
      grep -w inet6 | \
      grep -v scope | \
      awk '{ print $2 }' | \
      grep -Ew "^${addr}" >/dev/null 2>&1
   return $?
}

get_ipfw_nat_instance()
{
   local iface="${1}"
   local res=1

   if [ -z "${iface}" ] ; then
      local instance="`ipfw list|egrep '[0-9]+ nat'|awk '{ print $3 }'|tail -1`"
      if [ -z "${instance}" ] ; then
         instance="100"
      else		  
         : $(( instance += 100 )) 
      fi
      echo "${instance}"
      return 0
   fi

   for ni in `ipfw list|egrep '[0-9]+ nat'|awk '{ print $3 }'`
   do
      ipfw nat "${ni}" show config|egrep -qw "${iface}"
      if [ "$?" = "0" ] ; then
         echo "${ni}"
         res=0
         break
      fi
   done

   return ${res}
}

get_ipfw_nat_next_priority()
{
   local priority="${1}"

   priority=`echo "${priority}" + 1|bc`
   printf "%05d\n" "${priority}"
   return 0
}

get_ipfw_nat_priority()
{
   local iface="${1}"
   local res=1

   if [ -z "${iface}" ] ; then
      local priority="`ipfw list|egrep '[0-9]+ nat'|awk '{ print $1 }'|tail -1`"
      if [ -z "${priority}" ] ; then
         priority=2000
      fi
      printf "%05d\n" "${priority}"
      return 0
   fi

   local IFS='
'
   for rule in `ipfw list|egrep '[0-9]+ nat'`
   do
      local priority="`echo "${rule}"|awk '{ print $1 }'`"
      local ni="`echo "${rule}"|awk '{ print $3 }'`"

      ipfw nat "${ni}" show config|egrep -qw "${iface}"
      if [ "$?" = "0" ] ; then
         echo "${priority}"
         res=0
         break
      fi
   done

   return ${res}
}

get_template_path()
{
   local template="${1}"
   if [ -z "${template}" ] ; then
     return 1
   fi

   local tpath="${JDIR}/.warden-template-${template}"
   if [ ! -d "${tpath}" ] ; then
     return 1
   fi

   echo "${tpath}"
   return 0
}

get_template_os()
{
   local template="${1}"
   if [ -z "${template}" ] ; then
     return 1
   fi

   local tpath="${JDIR}/.warden-template-${template}"
   if [ ! -d "${tpath}" ] ; then
     return 1
   fi
   
   file "${tpath}/sbin/sysctl" | cut -d ',' -f 5 | awk '{ print $2 }' | cut -f2 -d'/'
   return 0
}

get_template_version()
{
   local template="${1}"
   if [ -z "${template}" ] ; then
     return 1
   fi

   local tpath="${JDIR}/.warden-template-${template}"
   if [ ! -d "${tpath}" ] ; then
     return 1
   fi

   file "${tpath}/sbin/sysctl" | cut -d ',' -f 5 | awk '{ print $3 }'
   return 0
}

get_template_arch()
{
   local template="${1}"
   if [ -z "${template}" ] ; then
     return 1
   fi

   local tpath="${JDIR}/.warden-template-${template}"
   if [ ! -d "${tpath}" ] ; then
     return 1
   fi

   local arch="$(file "${tpath}/sbin/sysctl" | awk '{ print $3 }')"
   if [ "${arch}" = "64-bit" ] ; then
     arch="amd64"
   else
     arch="i386"
   fi

   echo "${arch}"
   return 0
}

get_template_instances()
{
   local template="${1}"
   if [ -z "${template}" ] ; then
     return 1
   fi

   local tpath="${JDIR}/.warden-template-${template}"
   if [ ! -d "${tpath}" ] ; then
     return 1
   fi

   tank="$(getZFSTank "${tpath}")"
   rp="$(getZFSRelativePath "${tpath}")"
   td="${tank}${rp}"

   local ifs="${IFS}"
   IFS=$'\n'

   count=0
   for i in $(ls -d "${JDIR}"/.*.meta) ; do
     jail="$(basename "${i}"|sed -E 's/(^\.|\.meta)//g')"
     tank="$(getZFSTank "${JDIR}")"
     rp="$(getZFSRelativePath "${JDIR}")"
     jd="${tank}${rp}/${jail}"

     origin="$(zfs get -H origin "${jd}")"
     if [ -z "${origin}" ]; then continue; fi

     origin="${origin##"${jd}"}"
     if [ -z "${origin}" ]; then continue; fi

     origin="$(echo "${origin}" | sed -E 's|^([[:space:]]+origin[[:space:]]+)||')"
     if [ -z "${origin}" ]; then continue; fi

     origin="$(echo "${origin}" | sed -E 's|@.+$||')"
     if [ -z "${origin}" ]; then continue; fi

     if [ "${origin}" = "${td}" ] ; then
       : $(( count += 1 ))
     fi
   done

   IFS="${ifs}"
   echo "${count}"
   return 0
}

list_templates()
{
   local verbose="0"
   case "${1}" in 
     -v) verbose="1"
   esac

   if [ "${verbose}" = "0" ] ; then
     warden_print "Jail Templates:"
     warden_print "------------------------------"
   fi

   local ifs="${IFS}"
   IFS=$'\n'
   for i in `ls -d ${JDIR}/.warden-template* 2>/dev/null`
   do
      if [ ! -e "$i/bin/sh" ] ; then continue ; fi
      NICK=`echo "$i" | sed "s|${JDIR}/.warden-template-||g"`

      file "$i/sbin/sysctl" 2>/dev/null | grep -q "64-bit"
      if [ $? -eq 0 ] ; then
         ARCH="amd64"
      else
         ARCH="i386"
      fi
      VER=`file "$i/sbin/sysctl" | cut -d ',' -f 5 | awk '{print $3}'`
      OS=`file "$i/sbin/sysctl" | cut -d ',' -f 5 | awk '{print $2}'`
      if [ -e "$i/etc/rc.delay" ] ; then
         TYPE="TrueOS"
      elif echo "${OS}"|egrep -q Linux ; then
         TYPE="Linux"
      else
         TYPE="FreeBSD"
      fi
        
      if [ "${verbose}" = "0" ] ; then
        warden_print "${NICK} - $TYPE $VER ($ARCH)"

      else
        if [ "${verbose}" = "1" ] ; then
          INSTANCES="$(get_template_instances "${NICK}")" 

          out="$(mktemp  /tmp/.wjvXXXXXX)"
          cat<<__EOF__ >"${out}"

nick: ${NICK}
type: ${TYPE}
version: ${VER}
arch: ${ARCH}
instances: ${INSTANCES}

__EOF__
          warden_cat "${out}"
          rm -f "${out}"
        fi
     fi
   done
   IFS="${ifs}"
   exit 0
}

delete_template()
{
   tDir="${JDIR}/.warden-template-${1}"
   isDirZFS "${JDIR}"
   if [ $? -eq 0 ] ; then
     isDirZFS "${tDir}" "1"
     if [ $? -ne 0 ] ; then warden_error "Not a ZFS volume: ${tDir}" ; fi
     tank=`getZFSTank "$tDir"`
     rp=`getZFSRelativePath "$tDir"`
     zfs destroy -fr "$tank${rp}"
     rmdir ${tDir} >/dev/null 2>&1
   else
     if [ ! -e "${tDir}.tbz" ] ; then
       warden_exit "No such template: ${1}"
     fi
     rm "${tDir}.tbz"
   fi
   exit 0
}

rename_template()
{
   local oldname="${1}"
   local newname="${2}"
   local oldtDir="${JDIR}/.warden-template-${oldname}"
   local newtDir="${JDIR}/.warden-template-${newname}"

   isDirZFS "${JDIR}"
   if [ $? -eq 0 ] ; then
     isDirZFS "${oldtDir}" "1"
     if [ $? -ne 0 ] ; then warden_error "Not a ZFS volume: ${oldtDir}" ; fi
     tank=`getZFSTank "${oldtDir}"`
     oldrp=`getZFSRelativePath "${oldtDir}"`
     newrp=`getZFSRelativePath "${newtDir}"`

     zfs unmount -f "${tank}${oldrp}"
     zfs rename -f "${tank}${oldrp}" "${tank}${newrp}"
     zfs set mountpoint="/${tank}${newrp}" "${tank}${newrp}"
     zfs mount "${tank}${newrp}"

   else
     if [ ! -e "${oldtDir}.tbz" ] ; then
       warden_exit "No such template: ${oldname}"
     fi
     mv "${oldtDir}.tbz" "${newtDir}.tbz"
   fi
   exit 0
}

get_next_id()
{
   local jdir="${1}"
   local meta_id=0
   local ifs=${IFS}

   IFS=$'\n'
   if [ -d "${jdir}" ] ; then
      for i in `ls -d ${jdir}/.*.meta 2>/dev/null|grep -vw "${JAILNAME}"`
      do
        if [ ! -f "${i}/id" ] ; then continue ; fi

        id="$(cat "${i}/id" 2>/dev/null)"
        if [ "${id}" -gt "${meta_id}" ] ; then
          meta_id="${id}"
        fi
      done
   fi

   IFS="${ifs}"
   : $(( meta_id += 1 ))
   echo ${meta_id}
}

set_unique_id()
{
   local jdir="${1}"
   local meta_id=0

   set_warden_metadir

   lockf "/var/tmp/.jailid" \
      ${PROGDIR}/scripts/backend/jailid.sh "${JDIR}" "${JMETADIR}"

   return $?
}

get_freebsd_mirrors()
{
   cat<<-__EOF__
      ftp://ftp1.freebsd.org/pub/FreeBSD/releases
      ftp://ftp2.freebsd.org/pub/FreeBSD/releases
      ftp://ftp3.freebsd.org/pub/FreeBSD/releases
      ftp://ftp4.freebsd.org/pub/FreeBSD/releases
      ftp://ftp5.freebsd.org/pub/FreeBSD/releases
      ftp://ftp6.freebsd.org/pub/FreeBSD/releases
      ftp://ftp7.freebsd.org/pub/FreeBSD/releases
      ftp://ftp8.freebsd.org/pub/FreeBSD/releases
      ftp://ftp9.freebsd.org/pub/FreeBSD/releases
      ftp://ftp10.freebsd.org/pub/FreeBSD/releases
      ftp://ftp11.freebsd.org/pub/FreeBSD/releases
      ftp://ftp12.freebsd.org/pub/FreeBSD/releases
      ftp://ftp13.freebsd.org/pub/FreeBSD/releases
      ftp://ftp14.freebsd.org/pub/FreeBSD/releases
__EOF__
}

get_freebsd_mirror_list()
{
   local file="${1}"
   local freebsd_mirrors="$(get_freebsd_mirrors)"

   local mirrors=
   for m in ${freebsd_mirrors}
   do
       mirrors="${mirrors} ${m}/${1}"
   done

   echo "${mirrors}"
}

get_freebsd_file()
{
   local _rf="${1}"
   local _lf="${2}"

   local aDir="$(dirname "$_lf")"
   local aFile="$(basename "$_lf")"

   local astatfile="${HOME}/.fbsd-aria-stat-${ARCH}"
   if [ -e "${astatfile}" ] ; then
     local astat="--server-stat-of="${astatfile}"
        --server-stat-if="${astatfile}"
        --uri-selector=adaptive
        --server-stat-timeout=864000"
   else
     local astat=" --server-stat-of="${astatfile}" --uri-selector=adaptive "
   fi
   touch "$astatfile"

   local mirrors="$(get_freebsd_mirror_list "${1}")"

   aria2c -k 5M \
      ${astat} \
      --check-certificate=false \
      --file-allocation=none \
      -d "${aDir}" \
      -o "${aFile}" \
      ${mirrors}

   return $?
}


is_linux_jail()
{
   file "${JAILDIR}/sbin/sysctl" | \
      cut -d ',' -f 5 | \
      awk '{ print $2 }' | \
      cut -f2 -d'/' | \
      grep -iq Linux >/dev/null 2>&1
   if [ "$?" = "0" ] ; then
      return 0
   fi

   return 1
}

warden_host_entry_exists()
{
   local hostsfile="${1}"
   local entry="${2}"

   if [ ! -f "${hostsfile}" -o -z "${entry}" ] ; then
      return 1
   fi

   grep -qw "${entry}" "${hostsfile}"
   return $?
}

warden_host_entry_add()
{
   local hostsfile="${1}"
   local ip="${2}"

   if [ -z "${hostsfile}" -o -z "${ip}" ] ; then
      return 1
   fi

   shift; shift;
   local hosts="$*"
   if [ -z "${hosts}" ] ; then
      return 1
   fi

   printf "%s\t%s\n" "${ip}" "${hosts}" >> "${hostsfile}"
}

warden_host_entry_remove()
{
   local hostsfile="${1}"
   local entry="${2}"
   local tmpfile="$(mktemp /tmp/XXXXXX)"

   grep -wiv "${entry}" "${hostsfile}" < "${hostsfile}" > "${tmpfile}"
   mv "${tmpfile}" "${hostsfile}"
   chmod 644 "${hostsfile}"
}

warden_host_entry_modify()
{
   local hostsfile="${1}"
   local oldip="${2}"
   local newip="${3}"

   if [ ! -f "${hostsfile}" -o -z "${oldip}" -o -z "${newip}" ] ; then
      return 1
   fi

   local tmpfile="$(mktemp /tmp/XXXXXX)"
   awk -v oldip="${oldip}" -v newip="${newip}" '
      BEGIN { sub("/.+$", "", oldip); sub("/.+$", "", newip); }
      {
         if ($0 ~ oldip) {
            split($0, parts);
            if (parts[1] == oldip) {
               gsub(oldip, newip);
            }
         }

         print $0;
   }
   ' < "${hostsfile}" > "${tmpfile}"
   if [ "$?" = "0" ] ; then
      mv "${tmpfile}" "${hostsfile}"
      chmod 644 "${hostsfile}"
   fi
   rm -f "${tmpfile}"
}

warden_get_id()
{
   local dir="${1}"

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   cat "${dir}/id" 2>/dev/null
}

warden_get_host()
{
   local dir="${1}"

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   cat "${dir}/host" 2>/dev/null
}

warden_vnet_enabled()
{
   local dir="${1}"

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   local res=1
   if [ -e "${dir}/vnet" ] ; then
      res=0
   fi

   return ${res}
}

warden_nat_enabled()
{
   local dir="${1}"

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   local res=1
   if [ -e "${dir}/nat" ] ; then
      res=0
   fi

   return ${res}
}

warden_autostart_enabled()
{
   local dir="${1}"

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   local res=1
   if [ -e "${dir}/autostart" ] ; then
      res=0
   fi

   return ${res}
}

warden_get_jailtype()
{
   local dir="${1}"

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   cat "${dir}/jailtype" 2>/dev/null
}

warden_get_jailflags()
{
   local dir="${1}"

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   cat "${dir}/jail-flags" 2>/dev/null|tr ' ' ','
}

warden_get_iface()
{
   local dir="${1}"

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   cat "${dir}/iface" 2>/dev/null
}

warden_get_mac()
{
   local dir="${1}"

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   cat "${dir}/mac" 2>/dev/null
}

warden_get_ipv4()
{
   local dir="${1}"
   local strip="${2}"
   local ipv4=

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   if [ -n "${strip}" ] ; then
      strip="|cut -f1 -d'/'"
   fi

   ipv4="$(eval cat '"${dir}/ipv4"' 2>/dev/null ${strip})"

   echo "${ipv4}"
}

warden_get_ipv4_aliases()
{
   local dir="${1}"
   local strip="${2}"

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   if [ -n "${strip}" ] ; then
      strip="|cut -f1 -d'/'"
   fi

   ipv4_aliases= 
   if [ -e "${dir}/alias-ipv4" ] ; then
      while read line
      do
         line="$(eval echo "${line}" ${strip})"
         ipv4_aliases="${ipv4_aliases} ${line}"
      done < "${dir}/alias-ipv4"
   fi

   echo "${ipv4_aliases}"
}

warden_get_ipv4_defaultrouter()
{
   local dir="${1}"
   local strip="${2}"
   local filter=""

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   if [ -n "${strip}" ] ; then
      strip="|cut -f1 -d'/'"
   fi

   eval cat '"${dir}/defaultrouter-ipv4"' 2>/dev/null ${strip}
}

warden_get_ipv4_bridge()
{
   local dir="${1}"
   local strip="${2}"

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   if [ -n "${strip}" ] ; then
      strip="|cut -f1 -d'/'"
   fi

   eval cat '"${dir}/bridge-ipv4"' 2>/dev/null ${strip}
}

warden_get_ipv4_bridge_aliases()
{
   local dir="${1}"
   local strip="${2}"

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   if [ -n "${strip}" ] ; then
      strip="|cut -f1 -d'/'"
   fi

   ipv4_bridge_aliases= 
   if [ -e "${dir}/alias-bridge-ipv4" ] ; then
      while read line
      do
         line="$(eval echo "${line}" ${strip})"
         ipv4_bridge_aliases="${ipv4_bridge_aliases} $line"
      done < "${dir}/alias-bridge-ipv4"
   fi

   echo "${ipv4_bridge_aliases}"
}

warden_ipv4_isdhcp()
{
   local ipv4="$(warden_get_ipv4)"

   local ret=1
   if [ -n "${ipv4}" -a "${ipv4}" = "DHCP" ] ; then
      ret=0
   fi

   return ${ret}
}

warden_ipv4_isnull()
{
   local ipv4="$(warden_get_ipv4)"

   local ret=1
   if [ -z "${ipv4}" ] ; then
      ret=0
   fi

   return ${ret}
}

warden_set_ipv4()
{
   local newip="$(echo "${1}"|tr a-z A-Z)"
   local oldip="$(warden_get_ipv4)"
   local jaildir="${JDIR}/${JAILNAME}"
   local hosts="${jaildir}/etc/hosts"

   if [ "${newip}" = "DHCP" ] ; then
       echo "${newip}" > "${JMETADIR}/ipv4"
       return 0
   fi
   
   get_ip_and_netmask "${newip}"  
   newip="${JIP}"
   newmask="${JMASK}"

   if [ -z "${newip}" ] ; then
      rm -rf "${JMETADIR}/ipv4"
   fi

   if [ -z "${newmask}" ] ; then
      newmask="24"
   fi

   warden_host_entry_modify "${hosts}" "${oldip}" "${newip}"

   echo "${newip}/${newmask}" > "${JMETADIR}/ipv4"
}

warden_get_ipv6()
{
   local dir="${1}"
   local strip="${2}"
   local ipv6=

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   if [ -n "${strip}" ] ; then
      strip="|cut -f1 -d'/'"
   fi

   ipv6="$(eval cat '"${dir}/ipv6"' 2>/dev/null ${strip})"

   echo "${ipv6}"
}

warden_get_ipv6_aliases()
{
   local dir="${1}"
   local strip="${2}"

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   if [ -n "${strip}" ] ; then
      strip="|cut -f1 -d'/'"
   fi

   ipv6_aliases= 
   if [ -e "${dir}/alias-ipv6" ] ; then
      while read line
      do
         line="$(eval echo "${line}" ${strip})"
         ipv6_aliases="${ipv6_aliases} $line"
      done < "${dir}/alias-ipv6"
   fi

   echo "${ipv6_aliases}"
}

warden_get_ipv6_defaultrouter()
{
   local dir="${1}"
   local strip="${2}"

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   if [ -n "${strip}" ] ; then
      strip="|cut -f1 -d'/'"
   fi

   eval cat '"${dir}/defaultrouter-ipv6"' 2>/dev/null ${strip}
}

warden_get_ipv6_bridge()
{
   local dir="${1}"
   local strip="${2}"

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   if [ -n "${strip}" ] ; then
      strip="|cut -f1 -d'/'"
   fi

   eval cat '"${dir}/bridge-ipv6"' 2>/dev/null ${strip}
}

warden_get_ipv6_bridge_aliases()
{
   local dir="${1}"
   local strip="${2}"

   if [ -z "${dir}" ] ; then
      dir="${JMETADIR}"
   fi

   if [ -n "${strip}" ] ; then
      strip="|cut -f1 -d'/'"
   fi

   ipv6_bridge_aliases= 
   if [ -e "${dir}/alias-bridge-ipv6" ] ; then
      while read line
      do
         line="$(eval echo "${line}" ${strip})"
         ipv6_bridge_aliases="${ipv6_bridge_aliases} $line"
      done < "${dir}/alias-bridge-ipv6"
   fi

   echo "${ipv6_bridge_aliases}"
}

warden_ipv6_isautoconf()
{
   local ipv6="$(warden_get_ipv6)"

   local ret=1
   if [ -n "${ipv6}" -a "${ipv6}" = "AUTOCONF" ] ; then
      ret=0
   fi

   return ${ret}
}

warden_ipv6_isnull()
{
   local ipv6="$(warden_get_ipv6)"

   local ret=1
   if [ -z "${ipv6}" ] ; then
      ret=0
   fi

   return ${ret}
}

warden_set_ipv6()
{
   local newip="$(echo "${1}"|tr a-z A-Z)"
   local oldip="$(warden_get_ipv6)"
   local jaildir="${JDIR}/${JAILNAME}"
   local hosts="${jaildir}/etc/hosts"

   if [ "${newip}" = "AUTOCONF" ] ; then
       echo "${newip}" > "${JMETADIR}/ipv6"
       return 0
   fi

   newip="$(echo "${newip}"|tr A-Z a-z)"
   
   get_ip_and_netmask "${newip}"  
   newip="${JIP}"
   newmask="${JMASK}"

   if [ -z "${newip}" ] ; then
      rm -rf "${JMETADIR}/ipv6"
   fi

   if [ -z "${newmask}" ] ; then
      newmask="64"
   fi

   warden_host_entry_modify "${hosts}" "${oldip}" "${newip}"

   echo "${newip}/${newmask}" > "${JMETADIR}/ipv6"
}

warden_jail_isrunning()
{
   local jail="${1}"

   exec 4>&1
   err="$( ((jls -j "${jail}" 2>/dev/null || echo "0:$?" >&3) | \
      (grep -qw "${jail}" || echo "1:$?" >&3)) 3>&1 >&4 )"
   exec 4>&-

   [ -z "${err}" ]
}

warden_get_jailid()
{
   local jail1="${1}"
   local jail2="$(echo "${jail1}"|awk '{ print $1 }')"
   local jail="${jail1}"

   if ! warden_jail_isrunning "${jail}" ; then
      return 1
   fi

   if [ "${jail}" != "${jail2}" ] ; then
      jail="\"${jail}\""
   fi

   jail="$(jls name|awk -v jail="^${jail}\$" '$0 ~ jail { print $0 }')"
   if [ -z "${jail}" ] ; then
       return 1
   fi

   jls -j ${jail1} jid
   return $?
}

warden_add_ndp_entries()
{
   local jid="${1}"
   if [ -z "${jid}" ] ; then
      return 1
   fi

   for iface in $(ifconfig -l|sed -E 's#((bridge|epair|ipfw|lo)[0-9]+([^ ]+)?)##g')
   do
      if ifconfig ${iface} inet6|egrep -q inet6 2>/dev/null 2>&1
      then
         ether="$(ifconfig ${iface} ether|grep ether | awk '{ print $2 }')"
         for ip6 in $(ifconfig ${iface} inet6 | \
            grep inet6 | grep -v scope | awk '{ print $2 }')
         do
            if [ -n "${ether}" ] ; then
               warden_print "ndp -s ${ip6} ${ether}"
               jexec ${jid} ndp -s "${ip6}" "${ether}" >/dev/null 2>&1
            fi
         done
      fi
   done

   return 0
}
