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

warden_log() {
  if [ -n "${WARDEN_USESYSLOG}" ] ; then
    logger -t warden $*
  fi
  if [ -n "${WARDEN_LOGFILE}" ] ; then
    echo $* >> ${WARDEN_LOGFILE}
  fi
};

warden_printf() {
  if [ -n "${WARDEN_USESYSLOG}" ] ; then
    logger -t warden $*
  fi
  if [ -n "${WARDEN_LOGFILE}" ] ; then
    printf $* >> ${WARDEN_LOGFILE}
  fi
  printf $*
};

warden_cat() {
  if [ -n "${WARDEN_USESYSLOG}" ] ; then
    cat "$*" | logger -t warden
  fi
  if [ -n "${WARDEN_LOGFILE}" ] ; then
    cat "$*" >> ${WARDEN_LOGFILE}
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
      echo ${val} >> ${WARDEN_LOGFILE}
    fi
    echo ${val}
  done
};

warden_print() {
  if [ -n "${WARDEN_USESYSLOG}" ] ; then
    logger -t warden $*
  fi
  if [ -n "${WARDEN_LOGFILE}" ] ; then
    echo $* >> ${WARDEN_LOGFILE}
  fi
  echo "$*"
};

warden_error() {
  if [ -n "${WARDEN_USESYSLOG}" ] ; then
    logger -t warden "ERROR: $*"
  fi
  if [ -n "${WARDEN_LOGFILE}" ] ; then
    echo "ERROR: $*" >> ${WARDEN_LOGFILE}
  fi
  echo >&2 "ERROR: $*" 
};

warden_warn() {
  if [ -n "${WARDEN_USESYSLOG}" ] ; then
    logger -t warden "WARN: $*"
  fi
  if [ -n "${WARDEN_LOGFILE}" ] ; then
    echo "WARN: $*" >> ${WARDEN_LOGFILE}
  fi
  echo >&2 "ERROR: $*" 
};

warden_run() {
  local args="$*"

  if [ -n "${args}" ]
  then
    warden_print "${args}"
    ${args}
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
  cd ${JDIR}

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

  [ "$(md5 -q ${FBSD_TARBALL})" != "$(cat ${FBSD_TARBALL_CKSUM})" ] &&
    warden_error "Error in download data, checksum mismatch. Please try again later."

  # Creating ZFS dataset?
  isDirZFS "${JDIR}"
  if [ $? -eq 0 ] ; then
    trap "rmchroot ${CHROOT}" INT QUIT ABRT KILL TERM EXIT

    local zfsp=`getZFSRelativePath "${CHROOT}"`

    # Use ZFS base for cloning
    warden_print "Creating ZFS ${CHROOT} dataset..."
    tank=`getZFSTank "${JDIR}"`
    isDirZFS "${CHROOT}" "1"
    if [ $? -ne 0 ] ; then
       warden_print zfs create -o mountpoint=/${tank}${zfsp} -p ${tank}${zfsp}

       zfs create -o mountpoint=/${tank}${zfsp} -p ${tank}${zfsp}
       if [ $? -ne 0 ] ; then warden_exit "Failed creating ZFS base dataset"; fi
    fi

    warden_print tar xvpf ${FBSD_TARBALL} -C ${CHROOT}

    tar xvpf ${FBSD_TARBALL} -C ${CHROOT} 2>/dev/null
    if [ $? -ne 0 ] ; then warden_exit "Failed extracting ZFS chroot environment"; fi

    warden_print zfs snapshot ${tank}${zfsp}@clean

    zfs snapshot ${tank}${zfsp}@clean
    if [ $? -ne 0 ] ; then warden_exit "Failed creating clean ZFS base snapshot"; fi
    rm ${FBSD_TARBALL}

    trap INT QUIT ABRT KILL TERM EXIT

  else
    # Save the chroot tarball
    mv ${FBSD_TARBALL} ${CHROOT}
  fi
  rm ${FBSD_TARBALL_CKSUM}
};


rmchroot()
{
  local CHROOT="${1}"

  isDirZFS "${JDIR}"
  if [ $? -eq 0 ] ; then
    local zfsp=`getZFSRelativePath "${CHROOT}"`
    tank=`getZFSTank "${JDIR}"`

    warden_print "Destroying dataset ${tank}${zfsp}"
    zfs destroy -fR ${tank}${zfsp}
    if [ $? -ne 0 ] ; then warden_error "Failed to destroy ZFS base dataset"; fi

    warden_print "Removing ${CHROOT}"
    rm -rf ${CHROOT} >/dev/null 2>&1
    if [ $? -ne 0 ] ; then warden_error "Failed to remove chroot directory"; fi
  fi
};


### Mount all needed filesystems for the jail
mountjailxfs() {
  for nullfs_mount in ${NULLFS_MOUNTS}; do
    if [ ! -d "${JDIR}/${1}${nullfs_mount}" ] ; then
      mkdir -p "${JDIR}/${1}${nullfs_mount}"
    fi
    if is_symlinked_mountpoint ${nullfs_mount}; then
      warden_print "${nullfs_mount} has symlink as parent, not mounting"
      continue
    fi

    warden_print "Mounting ${JDIR}/${1}${nullfs_mount}"
    mount_nullfs ${nullfs_mount} ${JDIR}/${1}${nullfs_mount}
  done

  # Add support for linprocfs for ports that need linprocfs to build/run
  if [  ! -d "${JDIR}/${1}/compat/linux/proc" ]; then
    mkdir -p ${JDIR}/${1}/compat/linux/proc
  fi
  if is_symlinked_mountpoint ${JDIR}/${1}/compat/linux/proc; then
    warden_print "${JDIR}/${1}/compat/linux/proc has symlink as parent, not mounting"
    return
  fi
  warden_print "Enabling linprocfs support."
  mount -t linprocfs linprocfs ${JDIR}/${1}/compat/linux/proc
}

### Umount all the jail's filesystems
umountjailxfs() {
  status="0"
  # Umount all filesystems that are mounted into the portsjail
  for mountpoint in $(mount | grep ${JDIR}/${1}/ | cut -d" " -f3); do
    if [ "$mountpoint" = "${JDIR}/${1}/dev" ] ; then continue ; fi
    if [ "$mountpoint" = "${JDIR}/${1}/" ] ; then continue ; fi
    if [ "$mountpoint" = "${JDIR}/${1}" ] ; then continue ; fi
    echo "Unmounting $mountpoint"
    umount -f ${mountpoint}
    if [ $? -ne 0 ] ; then status="1" ; fi
  done
  # Now try to umount /dev
  umount -f ${JDIR}/${1}/dev 2>/dev/null >/dev/null
  return $status
}

# Check if PBI scripts are loaded in jail
checkpbiscripts() {
  if [ -z "${1}" ] ; then return ; fi
  if [ ! -e "${1}/usr/local/sbin/pbi_info" ] ; then
    copypbiscripts "${1}"
  elif [ "`ls -l /usr/local/sbin/pbi_info | awk '{print $5}'`" != "`ls -l ${1}/usr/local/sbin/pbi_info | awk '{print $5}'`" ] ; then 
    copypbiscripts "${1}"
  fi
}

# Copy PBI scripts to jail
copypbiscripts() {
  if [ -z "${1}" ] ; then return ; fi
  mkdir -p ${1}/usr/local/sbin >/dev/null 2>/dev/null
  cp /usr/local/sbin/pbi* ${1}/usr/local/sbin/
  chmod 755 ${1}/usr/local/sbin/pbi*

  # Copy rc.d pbid script
  mkdir -p ${1}/usr/local/etc/rc.d >/dev/null 2>/dev/null
  cp /usr/local/etc/rc.d/pbid ${1}/usr/local/etc/rc.d/

  # Copy any PBI manpages
  for man in `find /usr/local/man | grep pbi`
  do
    if [ ! -d "${1}`dirname $man`" ] ; then
      mkdir -p "${1}`dirname $man`"
    fi
    cp "${man}" "${1}${man}"
  done
}

mkportjail() {
  if [ -z "${1}" ] ; then return ; fi
  ETCFILES="resolv.conf passwd master.passwd spwd.db pwd.db group localtime"
  for file in ${ETCFILES}; do
    rm ${1}/etc/${file} >/dev/null 2>&1
    cp /etc/${file} ${1}/etc/${file}
  done
  
  # Need to symlink /home
  chroot ${1} ln -fs /usr/home /home

  # Make sure we remove our cleartmp rc.d script, causes issues
  [ -e "${1}/etc/rc.d/cleartmp" ] && rm ${1}/etc/rc.d/cleartmp
  # Flag this type
  touch ${JMETADIR}/jail-portjail
}

mkpluginjail() {
  if [ -z "${1}" ] ; then return ; fi
  ETCFILES="resolv.conf passwd master.passwd spwd.db pwd.db group localtime"
  for file in ${ETCFILES}; do
    rm ${1}/etc/${file} >/dev/null 2>&1
    cp /etc/${file} ${1}/etc/${file}
  done
  
  # Need to symlink /home
  chroot ${1} ln -fs /usr/home /home

  # Make sure we remove our cleartmp rc.d script, causes issues
  [ -e "${1}/etc/rc.d/cleartmp" ] && rm ${1}/etc/rc.d/cleartmp
  # Flag this type
  touch ${JMETADIR}/jail-pluginjail
}

mkZFSSnap() {
  isDirZFS "${1}" "1"
  if [ $? -ne 0 ] ; then warden_error "Not a ZFS volume: ${1}" ; fi
  tank=`getZFSTank "$1"`
  rp=`getZFSRelativePath "$1"`
  zdate=`date +%Y-%m-%d-%H-%M-%S`
  zfs snapshot $tank${rp}@$zdate
}

listZFSSnap() {
  isDirZFS "${1}" "1"
  if [ $? -ne 0 ] ; then warden_error "Not a ZFS volume: ${1}" ; fi
  tank=`getZFSTank "$1"`
  rp=`getZFSRelativePath "$1"`
  zfs list -t snapshot | grep -w "^${tank}${rp}" | cut -d '@' -f 2 | awk '{print $1}'
}

listZFSClone() {
  isDirZFS "${1}" "1"
  if [ $? -ne 0 ] ; then warden_error "Not a ZFS volume: ${1}" ; fi
  tank=`getZFSTank "$1"`
  cdir=`getZFSRelativePath "${CDIR}"` 
  warden_print "Clone Directory: ${CDIR}"
  warden_print "-----------------------------------"
  zfs list | grep -w "^${tank}${cdir}/${2}" | awk '{print $5}' | sed "s|${CDIR}/${2}-||g"
}

rmZFSClone() {
  CLONEDIR="${CDIR}/${3}-${2}"
  isDirZFS "${CLONEDIR}" "1"
  if [ $? -ne 0 ] ; then warden_error "Not a ZFS volume: ${CLONEDIR}" ; fi
  tank=`getZFSTank "${CLONEDIR}"`
  rp=`getZFSRelativePath "${CLONEDIR}"`
  zfs destroy ${tank}${rp}
}

rmZFSSnap() {
  isDirZFS "${1}" "1"
  if [ $? -ne 0 ] ; then warden_error "Not a ZFS volume: ${1}" ; fi
  tank=`getZFSTank "$1"`
  rp=`getZFSRelativePath "$1"`
  zfs destroy $tank${rp}@$2
}

revertZFSSnap() {
  isDirZFS "${1}" "1"
  if [ $? -ne 0 ] ; then warden_error "Not a ZFS volume: ${1}" ; fi
  tank=`getZFSTank "$1"`
  rp=`getZFSRelativePath "$1"`

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
  zfs rollback -R -f ${tank}${rp}@$2

  # If it was started, restart the jail now
  if [ "$restartJail" = "YES" ]; then
    ${PROGDIR}/scripts/backend/startjail.sh "${3}"
  fi
  
}

cloneZFSSnap() {
  isDirZFS "${1}" "1"
  if [ $? -ne 0 ] ; then warden_error "Not a ZFS volume: ${1}" ; fi
  tank=`getZFSTank "$1"`
  rp=`getZFSRelativePath "$1"`
  cdir=`getZFSRelativePath "${CDIR}"`

  # Make sure this is a valid snapshot
  zfs list -t snapshot | grep -w "^${tank}${rp}" | cut -d '@' -f 2 | awk '{print $1}' | grep -q ${2}
  if [ $? -ne 0 ] ; then warden_error "Invalid ZFS snapshot!" ; fi

  if [ -d "${CDIR}/${3}-${2}" ] ; then
     warden_error "This snapshot is already cloned and mounted at: ${CDIR}/${3}-${2}"
  fi

  # Clone the snapshot
  zfs clone -p ${tank}${rp}@$2 ${tank}${cdir}/${3}-${2}

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
   ifconfig ${1} | grep -w inet | awk '{ print $2 }'
}

get_interface_ipv4_addresses()
{
   ifconfig ${1} | grep -w inet | awk '{ print $2 }'
}

get_interface_ipv6_addresses()
{
   ifconfig ${1} | grep -w inet6 | awk '{ print $2 }'
}

get_interface_address()
{
   ifconfig ${1} | grep -w inet | head -1 | awk '{ print $2 }'
}

get_interface_ipv4_address()
{
   ifconfig ${1} | grep -w inet | head -1 | awk '{ print $2 }'
}

get_interface_ipv6_address()
{
   ifconfig ${1} | grep -w inet6 | head -1 | awk '{ print $2 }'
}

get_interface_aliases()
{
   local _count

   _count=`ifconfig ${1} | grep -w inet | wc -l`
   _count="$(echo "${_count} - 1" | bc)"

   ifconfig ${1} | grep -w inet | tail -${_count} | awk '{ print $2 }'
}

get_interface_ipv4_aliases()
{
   local _count

   _count=`ifconfig ${1} | grep -w inet | wc -l`
   _count="$(echo "${_count} - 1" | bc)"

   ifconfig ${1} | grep -w inet | tail -${_count} | awk '{ print $2 }'
}

get_interface_ipv6_aliases()
{
   local _count

   _count=`ifconfig ${1} | grep -w inet | wc -l`
   _count="$(echo "${_count} - 1" | bc)"

   ifconfig ${1} | grep -w inet6 | tail -${_count} | awk '{ print $2 }'
}

get_default_route()
{
   netstat -f inet -nr | grep '^default' | awk '{ print $2 }'
}

get_default_interface()
{
   netstat -f inet -nrW | grep '^default' | awk '{ print $7 }'
}

get_bridge_interfaces()
{
   ifconfig -a | grep -E '^bridge[0-9]+' | cut -f1 -d:
}

get_bridge_members()
{
   ifconfig ${1} | grep -w member | awk '{ print $2 }'
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

      jexec ${_jid} ifconfig ${_epairb} down
      ifconfig ${_epaira} down
      ifconfig ${_epaira} destroy
      _count=`ifconfig ${_bridgeif} | grep member | awk '{ print $2 }' | wc -l`
      if [ "${_count}" -le "1" ] ; then
         ifconfig ${_bridgeif} destroy
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
   for i in `ls -d ${JDIR}/.*.meta 2>/dev/null`
   do
      if [ -e "${i}/xjail" ] ; then
         touch ${i}/jail-portjail 2>/dev/null
      fi
      if [ -e "${i}/linuxjail" ] ; then
         touch ${i}/jail-linux 2>/dev/null
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

  mkdir -p ${1}/usr/local/bin
  mkdir -p ${1}/usr/local/share/pcbsd/conf
  mkdir -p ${1}/usr/local/share/pcbsd/distfiles

  cp /usr/local/bin/pc-extractoverlay ${1}/usr/local/bin/
  chmod 755 ${1}/usr/local/bin/pc-extractoverlay

  cp /usr/local/share/pcbsd/conf/server-excludes \
    ${1}/usr/local/share/pcbsd/conf
  cp /usr/local/share/pcbsd/distfiles/server-overlay.txz \
    ${1}/usr/local/share/pcbsd/distfiles

  return 0
}

make_bootstrap_pkgng_file_standard()
{
  local jaildir="${1}"
  local outfile="${2}"

  local release="$(uname -r | cut -d '-' -f 1-2)"
  local arch="$(uname -m)"

  get_mirror
  local mirror="${VAL}"

cat<<__EOF__>"${outfile}"
#!/bin/sh

ret=0

tar xvf pkg.txz --exclude +MANIFEST --exclude +MTREE_DIRS 2>/dev/null
pkg add pkg.txz
rm pkg.txz

mount -t devfs devfs /dev

echo "PACKAGESITE: ${mirror}/packages/${release}/${arch}" >/usr/local/etc/pkg.conf
echo "HTTP_MIRROR: http" >>/usr/local/etc/pkg.conf
echo "PUBKEY: /usr/local/etc/pkg-pubkey.cert" >>/usr/local/etc/pkg.conf
echo "PKG_CACHEDIR: /usr/local/tmp" >>/usr/local/etc/pkg.conf

__EOF__

echo '
i=0
percent=30

pkg update
if [ "$?" != "0" ]
then
   umount -f devfs
   touch /FAIL
   exit 4
fi

total=`pkg rquery "%do" pcbsd-utils|wc -l| awk '"'{ print '"'$1'"' }'"'`
for p in `pkg rquery "%do" pcbsd-utils`
do
  pkg install -y ${p}
  if [ "$?" != "0" ]
  then
      umount -f devfs
      touch /FAIL
      exit 5
  fi

  if [ "${i}" -ge "0" ]
  then  
      percent=`echo "scale=2;((${i}/${total})*70)+30"|bc|cut -f1 -d.`
  fi
  echo "===== ${percent}% ====="

  : $(( i += 1 ))
done
pkg install -y pcbsd-utils

umount -f devfs
exit 0
' >> "${outfile}"
}

make_bootstrap_pkgng_file_pluginjail()
{

  local jaildir="${1}"
  local outfile="${2}"

  local release="$(uname -r | cut -d '-' -f 1-2)"
  local arch="$(uname -m)"

  get_mirror
  local mirror="${VAL}"

  cp /usr/local/share/warden/pluginjail-packages "${jaildir}/pluginjail-packages"

cat<<__EOF__>"${outfile}"
#!/bin/sh

i=0
ret=0
percent=10

tar xvf pkg.txz --exclude +MANIFEST --exclude +MTREE_DIRS 2>/dev/null
pkg add pkg.txz
rm pkg.txz

mount -t devfs devfs /dev

echo "PACKAGESITE: ${mirror}/packages/${release}/${arch}" >/usr/local/etc/pkg.conf
echo "HTTP_MIRROR: http" >>/usr/local/etc/pkg.conf
echo "PUBKEY: /usr/local/etc/pkg-pubkey.cert" >>/usr/local/etc/pkg.conf
echo "PKG_CACHEDIR: /usr/local/tmp" >>/usr/local/etc/pkg.conf

__EOF__

echo '
pkg update
if [ "$?" != "0" ]
then
   umount devfs
   touch /FAIL
   exit 4
fi

count1=`pkg rquery "%do" pcbsd-utils|wc -l| awk '"'{ print '"'$1'"' }'"'`
count2=`cat /pluginjail-packages|wc -l|awk '"'{ print '"'$1'"' }'"'`
total=`echo "${count1} + ${count2}" | bc`

for p in `pkg rquery "%do" pcbsd-utils`
do
  pkg install -y ${p}
  if [ "$?" != "0" ]
  then
      umount -f devfs
      touch /FAIL
      exit 5
  fi

  if [ "${i}" -ge "0" ]
  then  
      percent=`echo "scale=2;((${i}/${total})*90)+10"|bc|cut -f1 -d.`
  fi
  echo "===== ${percent}% ====="

  : $(( i += 1 ))
done
pkg install -y pcbsd-utils

for p in `cat /pluginjail-packages`
do
  pkg install -y ${p}
  if [ "$?" != "0" ]
  then
      umount -f devfs
      touch /FAIL
      exit 6
  fi

  if [ "${i}" -ge "0" ]
  then  
      percent=`echo "scale=2;((${i}/${total})*90)+10"|bc|cut -f1 -d.`
  fi
  echo "===== ${percent}% ====="

  : $(( i += 1 ))
done

umount -f devfs
exit 0
' >> "${outfile}"
}


bootstrap_pkgng()
{
  local jaildir="${1}"
  local jailtype="${2}"
  if [ -z "${jailtype}" ] ; then
    jailtype="standard"
  fi
  local release="$(uname -r | cut -d '-' -f 1-2)"
  local arch="$(uname -m)"

  local ffunc="make_bootstrap_pkgng_file_standard"
  if [ "${jailtype}" = "pluginjail" ] ; then
    ffunc="make_bootstrap_pkgng_file_pluginjail"
  fi

  cd ${jaildir} 
  warden_print "Boot-strapping pkgng"

  mkdir -p ${jaildir}/usr/local/etc
  pubcert="/usr/local/etc/pkg-pubkey.cert"

  cp "${pubcert}" ${jaildir}/usr/local/etc
  install_pc_extractoverlay "${jaildir}"

  ${ffunc} "${jaildir}" "${jaildir}/bootstrap-pkgng"
  chmod 755 "${jaildir}/bootstrap-pkgng"

  if [ -e "pkg.txz" ] ; then rm pkg.txz ; fi
  get_file_from_mirrors "/packages/${release}/${arch}/Latest/pkg.txz" "pkg.txz"
  if [ $? -eq 0 ] ; then
    warden_print chroot ${jaildir} /bootstrap-pkgng

    chroot ${jaildir} /bootstrap-pkgng | warden_pipe
    if [ ! -e "${jaildir}/FAIL" ] ; then
       rm -f "${jaildir}/bootstrap-pkgng"
       rm -f "${jaildir}/pluginjail-packages"
       warden_print chroot ${jaildir} pc-extractoverlay server --sysinit
       chroot ${jaildir} pc-extractoverlay server --sysinit | warden_pipe
       return 0
    fi
  fi
  rm -f "${jaildir}/FAIL"

  warden_error "Failed boot-strapping PKGNG, most likely cause is internet connection failure."
  rm -f "${jaildir}/bootstrap-pkgng"
  rm -f "${jaildir}/pluginjail-packages"
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

   ${jexec} ifconfig "${iface}" | grep -qw inet 2>/dev/null
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

   ${jexec} ifconfig "${iface}" | \
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

   ${jexec} ifconfig "${iface}" | grep -qw inet6 2>/dev/null
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

   ${jexec} ifconfig "${iface}" | \
      grep -w inet6 | \
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

list_templates()
{
   warden_print "Jail Templates:"
   warden_print "------------------------------"
   isDirZFS "${JDIR}"
   if [ $? -eq 0 ] ; then
     for i in `ls -d ${JDIR}/.warden-template* 2>/dev/null`
     do
        if [ ! -e "$i/bin/sh" ] ; then continue ; fi
        NICK=`echo "$i" | sed "s|${JDIR}/.warden-template-||g"`
        file "$i/bin/sh" 2>/dev/null | grep -q "64-bit"
        if [ $? -eq 0 ] ; then
           ARCH="amd64"
        else
           ARCH="i386"
        fi
        VER=`file "$i/bin/sh" | cut -d ',' -f 5 | awk '{print $3}'`
        if [ -e "$i/etc/rc.delay" ] ; then
           TYPE="TrueOS"
        else
           TYPE="FreeBSD"
        fi
        warden_print "${NICK} - $TYPE $VER ($ARCH)"
     done
   else
     # UFS, no details for U!
     ls ${JDIR}/.warden-template*.tbz | sed "s|${JDIR}/.warden-template-||g" | sed "s|.tbz||g"
   fi
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
     zfs destroy -r $tank${rp}
     rmdir ${tDir}
   else
     if [ ! -e "${tDir}.tbz" ] ; then
       warden_exit "No such template: ${1}"
     fi
     rm ${tDir}.tbz
   fi
   exit 0
}

get_next_id()
{
   local jdir="${1}"
   local meta_id=0

   if [ -d "${jdir}" ] ; then
      for i in `ls -d ${jdir}/.*.meta 2>/dev/null`
      do
        id=`cat ${i}/id`
        if [ "${id}" -gt "${meta_id}" ] ; then
          meta_id="${id}"
        fi
      done
   fi

   : $(( meta_id += 1 ))
   echo ${meta_id}
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

   local aDir="$(dirname $_lf)"
   local aFile="$(basename $_lf)"

   local astatfile="${HOME}/.fbsd-aria-stat"
   if [ -e "${astatfile}" ] ; then
     local astat="--server-stat-of=${astatfile}
        --server-stat-if=${astatfile}
        --uri-selector=adaptive
        --server-stat-timeout=864000"
   else
     local astat=" --server-stat-of=${astatfile} --uri-selector=adaptive "
   fi
   touch $astatfile

   local mirrors="$(get_freebsd_mirror_list ${1})"

   aria2c -k 5M \
      ${astat} \
      --check-certificate=false \
      --file-allocation=none \
      -d ${aDir} \
      -o ${aFile} \
      ${mirrors}

   return $?
}
