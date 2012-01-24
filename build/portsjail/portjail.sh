#!/bin/sh
# Script to manage the Port Jail
#############################################################

PJDIR="/usr/jails/portjail"
PBREG="/usr/local/bin/pbreg"
JAILME="/usr/local/sbin/jailme"
PJHOST="$(hostname)"
ARCH="$(uname -m)"
ID="$(id -u)"
# Default pcbsd.conf file
PCBSD_ETCCONF="/usr/local/etc/pcbsd.conf"
# Set manpath to enable whatis to work
MANPATH="/usr/local/man" ; export MANPATH
MIN_FBSD_VERSION=9
# A list of directories that are mounted into the jail
NULLFS_MOUNTS="/tmp /media /usr/home /usr/src"

### Usage and exit
display_help() {
  echo "PC-BSD Port Jail Management"
  echo "--------------------------------"
  echo "Usage:"
  echo "  portjail start 	- Starts the jail, root only"
  echo "  portjail stop  	- Stops the jail, root only"
  echo "  portjail restart 	- Restarts the jail, root only"
  echo "  portjail console  	- Starts a shell session within the jail"
  echo "  portjail run <cmd>  	- Runs the specified command within the jail"
  echo "  portjail init  	- Setup the jail environment"
  echo "  portjail status       - Show the portjail's status"
  echo "  portjail delete  	- Deletes the jail"

  exit 1
}

### Print an error on STDERR and bail out
printerror() {
  echo >&2 "$*"
  echo "Press ENTER to continue" 
  read tmp
  exit 1
}

### Check if we're running PCBSD or FreeBSD
checkpcbsd() {
  if [ -e "${PCBSD_ETCCONF}" -a -e "${PBREG}" ]; then
    ISPCBSD="true"
    SYSVER="$(pbreg get /PC-BSD/Version)"
    FBSD_TARBALL="fbsd-release.tbz"
    FBSD_TARBALL_CKSUM="${FBSD_TARBALL}.md5"
  else
    ISPCBSD=""
    SYSVER="$(uname -r | cut -d- -f1-2)"
    FBSD_TARBALL="base.txz"
    FBSD_TARBALL_CKSUM="MANIFEST"
    [ $(echo ${SYSVER} | sed 's/^\([0-9][^.-]*\).*/\1/') -lt ${MIN_FBSD_VERSION} ] &&
      printerror "Sorry, you need at least FreeBSD ${MIN_FBSD_VERSION}."
  fi
}

### Check if the running user is root
checkroot() {
  if [ ${ID} -ne 0 ]; then
    [ -n "$1" ] && echo checkroot "Error: You must be root to $1 the ports jail."
    exit 1
  fi
  return 0
}

### Check if the jail is installed or not
checkjailinstalled() {
  if [ -d "${PJDIR}/etc" ]; then
    return 0
  else
    return 1
  fi
}

### Check if the jail is currently running
checkjailrunning() {
  jailrunning="$(jls | awk -v PJDIR=${PJDIR} '$4 == PJDIR {print $4}')"
  if [ -n "${jailrunning}" ]; then
    return 0
  else
    return 1
  fi
}

### Warn and exit if the jail is not yet installed
checkinitneeded() {
  if [ "$1" = "rc" ]; then
    checkjailinstalled || echo "Error: The jail is not installed. Please run 'portjail init' as root."
    checkjailinstalled || exit 0
  else
    checkjailinstalled || printerror "Error: The jail is not installed. Please run 'portjail init' as root."
  fi
}

### Check if jailme is installed
checkjailme() {
  [ -e ${JAILME} ] || printerror "You need to install sysutils/jailme first."
}

### Download the PCBSD version of the portsjail
downloadpcbsd() {
  # Set the mirror URL, may be overridden by setting MIRRORURL environment variable
  if [ -z "${MIRRORURL}" ]; then
    MIRRORURL="$(grep ^PCBSD_MIRROR: ${PCBSD_ETCCONF} | cut -d' ' -f2)"
    # Use the default mirror, if no other mirror is found.
    [ -z "${MIRRORURL}" ] && MIRRORURL="ftp://ftp.pcbsd.org/pub/mirror"
  fi

  cd ${PJDIR}

  echo "Fetching PC-BSD environment. This may take a while..."
  echo "Downloading ${MIRRORURL}/${SYSVER}/${ARCH}/netinstall/${FBSD_TARBALL} ..."
  fetch -a ${MIRRORURL}/${SYSVER}/${ARCH}/netinstall/${FBSD_TARBALL} \
           ${MIRRORURL}/${SYSVER}/${ARCH}/netinstall/${FBSD_TARBALL_CKSUM}
  [ $? -ne 0 ] && printerror "Error while downloading the portsjail."

  [ "$(md5 -q ${FBSD_TARBALL})" != "$(cat ${FBSD_TARBALL_CKSUM})" ] &&
    printerror "Error in download data, checksum mismatch. Please try again later."

  echo "Extracting FreeBSD environment... This may take a while..."
  tar xvpf ${FBSD_TARBALL} -C ${PJDIR}
  # Cleanup
  rm ${FBSD_TARBALL} ${FBSD_TARBALL_CKSUM}
}

### Download a plain FreeBSD base.txz
downloadfreebsd() {
  echo ${SYSVER} | egrep -q '(CURRENT)|(STABLE)'
  if [ $? -eq 0 ]; then
    echo "It appears that there are no pre-compiled tarballs for your version ${SYSVER}."
    echo "You may use the compile option (c), or provide a different release name, e.g."
    echo "9.0-RELEASE"
    read ANSWER
    if [ "${ANSWER}" = "c" ]; then
      PJMETHOD="b"
      initjail
    else
      SYSVER="${ANSWER}"
    fi 
  fi
    echo "You may enter a mirror server manually, else ftp.freebsd.org is used: [ftp.frebsd.org]"
    read PJAILMIRROR
    echo "Which protocol do you want to use ftp or http? [ftp]"
    read PROTOCOL
    [ -z "${PJAILMIRROR}" ] && PJAILMIRROR="ftp.freebsd.org"
    [ -z "${PROTOCOL}" ] && PROTOCOL="ftp"
    cd ${PJDIR}
    echo "Fetching FreeBSD environment. This may take a while..."
    echo "Downloading ${PROTOCOL}://${PJAILMIRROR}/pub/FreeBSD/releases/${ARCH}/${ARCH}/${SYSVER}/${FBSD_TARBALL}"
    fetch -a ${PROTOCOL}://${PJAILMIRROR}/pub/FreeBSD/releases/${ARCH}/${ARCH}/${SYSVER}/${FBSD_TARBALL}
    [ $? -ne 0 ] && printerror "Error: Download failed!"
    fetch -a ${PROTOCOL}://${PJAILMIRROR}/pub/FreeBSD/releases/${ARCH}/${ARCH}/${SYSVER}/${FBSD_TARBALL_CKSUM}
    [ $? -ne 0 ] && printerror "Error: Download failed!"

    [ "$(sha256 -q ${FBSD_TARBALL})" != \
      "$(awk -v FBSD_TARBALL=${FBSD_TARBALL} '$1 == FBSD_TARBALL {print $2}' ${FBSD_TARBALL_CKSUM})" ] &&
      printerror "Error in download data, checksum mismatch. Please try again later."

    tar --unlink -xvpJf ${FBSD_TARBALL}
    [ $? -ne 0 ] && printerror "Error: Extraction failed!"
    rm ${FBSD_TARBALL} ${FBSD_TARBALL_CKSUM}
}

### Mount all needed filesystems for the jail
mountjailfs() {
  for nullfs_mount in ${NULLFS_MOUNTS}; do
    mount_nullfs ${nullfs_mount} ${PJDIR}${nullfs_mount}
  done

  mount -t devfs devfs ${PJDIR}/dev
  mount -t procfs procfs ${PJDIR}/proc

  # Add support for linprocfs for ports that need linprocfs to build/run
  if [ -d "${PJDIR}/compat/linux/proc" ]; then
    mount -t linprocfs linprocfs ${PJDIR}/compat/linux/proc
  else
    echo "/compat/linux/proc does not exist. Adding linprocfs support."
    mkdir -p ${PJDIR}/compat/linux/proc
    mount -t linprocfs linprocfs ${PJDIR}/compat/linux/proc
  fi
}

### Umount all the jail's filesystems
umountjailfs() {
  # Umount all filesystems that are mounted into the portsjail
  for mountpoint in $(mount | grep ${PJDIR} | cut -d" " -f3); do
    umount -f ${mountpoint} || return 1
  done
}

### Start the jail
startjail() {
  [ ! -d "${PJDIR}/etc" -a "$1" = "rc" ] && exit 0

  echo "Starting the portjail..."
  # Create some hard-links for the portjail
  ETCFILES="resolv.conf passwd master.passwd spwd.db pwd.db group localtime"
  for file in ${ETCFILES}; do
    rm ${PJDIR}/etc/${file} >/dev/null 2>&1
    cp /etc/${file} ${PJDIR}/etc/${file}
  done

  # Figure out our default interfaces, otherwise try all.
  # Get the first IP address we find that is not special and use that for the jail.
  IP6_DFLT_IFACE=$(netstat -Warn -f inet6 | awk '/^default/ { print $7 }')
  IP4_DFLT_IFACE=$(netstat -Warn -f inet  | awk '/^default/ { print $7 }')
  [ -z "${IP6_DFLT_IFACE}" ] && IP6_DFLT_IFACE="-a"
  [ -z "${IP4_DFLT_IFACE}" ] && IP4_DFLT_IFACE="-a"
  PJIP6=$(ifconfig ${IP6_DFLT_IFACE} inet6 | awk '{ if (/fe80:/) { next; }; if (/ ::1 /) { next; }; if (/inet6 /) { print $2 }; }' | head -1)
  PJIP4=$(ifconfig ${IP6_DFLT_IFACE} inet | awk '{ if (/127.0.0./) { next; }; if (/inet /) { print $2 }; }' | head -1)
  PJIP="ip6.addr=${PJIP6}"
  if [ -n "${PJIP}" -a -n "${PJIP4}" ]; then
	PJIP="${PJIP} ip4.addr=${PJIP4}"
  elif [ -n "${PJIP4}" ]; then
	PJIP="ip4.addr=${PJIP4}"
  fi

  # Make sure we remove our cleartmp rc.d script, causes issues
  [ -e "${PJDIR}/etc/rc.d/cleartmp" ] && rm ${PJDIR}/etc/rc.d/cleartmp

  # Add the hostname to the portjails /etc/hosts file, to prevent sendmail warnings
  if [ -e ${PJDIR} ]; then
    sed -i -e '/^127.0.0.1.*/d' ${PJDIR}/etc/hosts
    sed -i -e '/^::1.*/d' ${PJDIR}/etc/hosts
  fi
  echo "::1		localhost localhost.my.domain ${PJHOST}" >>${PJDIR}/etc/hosts
  echo "127.0.0.1	localhost localhost.my.domain ${PJHOST}" >>${PJDIR}/etc/hosts

  # Make sure the /etc/rc.conf HOSTNAME values match
  : > ${PJDIR}/etc/rc.conf
  cat > ${PJDIR}/etc/rc.conf <<-EOF
hostname="$PJHOST"
cron_enable="NO"
syslogd_enable="NO"
sendmail_enable="NO"
sendmail_submit_enable="NO"
sendmail_outbound_enable="NO"
sendmail_msp_queue_enable="NO"
EOF

  # Mount all needed filesystems into the portjail path
  mountjailfs
  # Actually create and start the jail
  jail -c name=portjail path=${PJDIR} host.hostname=${PJHOST} ${PJIP} persist
  jexec portjail /bin/sh /etc/rc
}

### Stop the jail
stopjail() {
  [ ! -d "${PJDIR}/etc" -a "$1" = "rc" ] && exit 0

  echo "Stopping the portjail..."
  # Stop the Jail
  jexec portjail /bin/sh /etc/rc.shutdown
  jail -r portjail

  # Unmount all of the portjail's filesystems
  umountjailfs

}

### Start a console inside the jail
jailconsole() {
  DBUS_SESSION_BUS_ADDRESS="" ; export DBUS_SESSION_BUS_ADDRESS
  PJID=$(jls -s -j portjail -n jid | awk -F= '{ print $2 }')
  ${JAILME} ${PJID} /bin/csh
}

### Run a command inside the jail
runjailcommand() {
  [ -z "$1" ] && printerror "Error: No command specified!"

  DBUS_SESSION_BUS_ADDRESS="" ; export DBUS_SESSION_BUS_ADDRESS
  PJID=$(jls -s -j portjail -n jid | awk -F= '{ print $2 }')
  ${JAILME} ${PJID} "$1"
}

### Show some information about the jail
checkstatus() {
  checkjailinstalled || installed=" not"
  checkjailrunning   || running=" not"
  echo "Portjail is${installed} installed."
  echo "Portjail is${running} running."
  [ -z "${installed}" ] &&
    echo "There are $(PKG_DBDIR=${PJDIR}/var/db/pkg pkg_info 2>/dev/null | grep -c .) packages installed."
  exit 0
}

### Build / download, install and setup the jail
initjail() {
  # Setup a new portjail
  if [ -d ${PJDIR}/etc ]; then
     echo "The portsjail is already initialized. Re-initializing it will delete its"
     echo "contents. Do you want to continue? [y|n]"
     read DOIT
     if [ "${DOIT}" = "y" ]; then
       # Unmount first, so we don't delete /home and stuff :)
       umountjailfs
       if [ $? -eq 0 ]; then
         rm -r ${PJDIR}
       else
         printerror "Error: An error occured while unmounting the portjail filesystems. \
         	   Aborting re-initialization. Please check if there are any files opened \
         	   in one of the portjails's filesystems and try again after closing them."
       fi
     else
       exit 1
     fi
   fi

  while [ "${PJMETHOD}" != "d" -a "${PJMETHOD}" != "b" ]; do
    printf "Would you like to download a pre-compiled base jail from a FreeBSD mirror via\n"
    printf "FTP/HTTP or would you like to build one from source? Enter d for download or\n"
    printf "b to build from source: [d/b] "
    read PJMETHOD
    printf "\n"
  done

  # Create the jail dir
  [ ! -d "${PJDIR}" ] && mkdir -p "${PJDIR}"

  case "${PJMETHOD}" in
    b)
    if [ ! -e "/usr/src/COPYRIGHT" ]
    then
      echo "Error: You will need a copy of FreeBSD sources in /usr/src to build the portjail."
      echo "You may checkout sources via the System Manager, CVS, SVN or other method."
      exit 1
    fi

    # Preparing to build the jail
    echo "Starting build of portsjail, this may take a while..."
    sleep 5
    cd /usr/src
    make buildworld installworld distribution DESTDIR=${PJDIR}
    [ $? -ne 0 ] &&
      printerror "Error: The portjail build failed! Please check your sources and try again."
    ;;

    d)
    if [ -n "${ISPCBSD}" ]; then
      downloadpcbsd
    else
      downloadfreebsd
    fi
    echo "Extraction finished."
    ;;

    *)
    # NOTREACHED
    ;;
  esac

  # Make the home link
  mkdir -p ${PJDIR}/usr/home
  ln -sf /usr/home ${PJDIR}/home

  echo "Portjail setup finished! Please run 'portjail start' to enable the jail."
}

deletejail() {
  umountjailfs
  if [ $? -ne 0 ] ; then
    echo "Failed unmounting the jail!"
    exit 1
  fi
  echo "Deleting portjail: ${PJDIR}"
  chflags -R noschg ${PJDIR}
  rm -rf ${PJDIR}
  echo "Portjail deleted."
}

########################## MAIN ###############################

# if we are called without a flag, warn the user and exit
[ -z "$1" ] && display_help

case "$1" in
  start)
  checkinitneeded $2
  checkroot $1
  checkjailrunning || startjail $2
  ;;

  stop)
  # The portjail gets only stopped if the jail is installed and we're root.
  checkinitneeded $2
  checkroot $1
  checkjailrunning && stopjail $2 || printerror "The jail is not running."
  ;;

  restart)
  checkinitneeded
  checkroot $1
  checkjailrunning && stopjail $2 || printerror "The jail is not running."
  startjail $2
  ;;

  console)
  # Check if the portjail is already installed and running
  checkinitneeded
  checkjailme
  checkjailrunning && jailconsole || printerror "The jail is not running."
  ;;

  run)
  checkinitneeded
  checkjailme
  checkjailrunning && runjailcommand $2 || printerror "The jail is not running."
  ;;

  init)
  checkroot $1
  checkpcbsd
  if ! checkjailrunning && ! checkjailinstalled; then
    initjail
  else
    printerror "The jail is already installed."
  fi
  ;;
  status)
  checkstatus
  ;;

  delete)
  checkroot $1
  echo "You are about to delete the portjail. Do you really want to continue? [y|n]"
  read DELETE
  if [ "${DELETE}" = "y" ]; then
    checkjailrunning && stopjail $2
    deletejail
  fi
  ;;

  *)
  display_help
  ;;

esac

