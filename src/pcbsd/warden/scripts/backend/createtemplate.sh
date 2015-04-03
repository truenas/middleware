#!/bin/sh
# Script to create a new jail template
#####################################################################

# Source our functions
PROGDIR="/usr/local/share/warden"

# Source our variables
. ${PROGDIR}/scripts/backend/functions.sh

### Download the template files
download_template_files() {

  # Create the download directory
  if [ -d "${JDIR}/.download" ] ; then rm -rf "${JDIR}/.download"; fi
  mkdir "${JDIR}/.download"

  if [ ! -d "${JDIR}" ] ; then mkdir -p "${JDIR}" ; fi
  cd "${JDIR}"

  warden_print "Fetching jail environment. This may take a while..."
  if [ -n "$TRUEOSVER" ] ; then
     for f in $DFILES
     do
       get_file_from_mirrors "/${TRUEOSVER}/${FBSDARCH}/dist/$f" "${JDIR}/.download/$f" "iso"
       if [ $? -ne 0 ] ; then
         warden_exit "Failed downloading: /${TRUEOS}/${FBSDARCH}/dist/${f}"
       fi
     done
  else
     
     # Check if we are on REAL old versions of FreeBSD
     if [ "$oldFBSD" = "YES" ] ; then
	 # Get the .inf list file
         warden_run fetch -o "${JDIR}/.download/${oldStr}.inf" "http://ftp-archive.freebsd.org/pub/FreeBSD-Archive/old-releases/${FBSDARCH}/${FBSDVER}/${oldStr}/${oldStr}.inf"
	 if [ $? -ne 0 ] ; then
           warden_exit "Failed downloading: FreeBSD ${FBSDVER} - ${oldStr}.inf"
	 fi
	 # Now read in the list of files to fetch
	 while read line
	 do
	    echo "$line" | grep -q '^cksum'
	    if [ $? -ne 0 ] ; then continue ; fi
	    fName=`echo $line | cut -d " " -f 1 | sed "s|cksum|$oldStr|g"`
            fetch -o "${JDIR}/.download/$fName" "http://ftp-archive.freebsd.org/pub/FreeBSD-Archive/old-releases/${FBSDARCH}/${FBSDVER}/${oldStr}/$fName"
	    if [ $? -ne 0 ] ; then
              warden_exit "Failed downloading: FreeBSD ${FBSDVER} - $fName"
	    fi
	 done < "${JDIR}/.download/${oldStr}.inf"
	 return
     fi

     for f in $DFILES
     do
       warden_print get_freebsd_file "${FBSDARCH}/${FBSDVER}/${f}" "${JDIR}/.download/$f"
       if [ ! -f "${DISTFILESDIR}/${f}" ] ; then
         get_freebsd_file "${FBSDARCH}/${FBSDVER}/${f}" "${JDIR}/.download/$f"
         if [ $? -ne 0 ] ; then
	   warden_print "Trying ftp-archive..."
           warden_run fetch -o "${JDIR}/.download/$f" "http://ftp-archive.freebsd.org/pub/FreeBSD-Archive/old-releases/${FBSDARCH}/${FBSDVER}/$f"
           if [ $? -ne 0 ] ; then
             warden_exit "Failed downloading: FreeBSD ${FBSDVER}"
	   fi
         fi
         mv "${JDIR}/.download/${f}" "${DISTFILESDIR}/${f}"
         sha256 -q "${DISTFILESDIR}/${f}" > "${DISTFILESDIR}/${f}.sha256"
       fi
       show_progress
     done
  fi
};

create_template()
{
  # Creating ZFS dataset?
  isDirZFS "${JDIR}"
  if [ $? -eq 0 ] ; then
    local zfsp="`getZFSRelativePath "${TDIR}"`"

    # Use ZFS base for cloning
    tank="`getZFSTank "${JDIR}"`"

    mnt="`getZFSMountpoint ${tank}`"
    tdir="${mnt}${zfsp}"

    clean_exit()
    {
       cd /
       zfs destroy -fr "${tank}${zfsp}"
       find "${tdir}"|xargs chflags noschg 
       rm -rf "${tdir}" >/dev/null 2>&1
       rm -rf "${EXTRACT_TARBALL_STATUSFILE}"
       warden_exit "Failed to create ZFS base dataset"
    }

    trap clean_exit INT QUIT ABRT KILL TERM EXIT

    isDirZFS "${TDIR}" "1"
    if [ $? -ne 0 ] ; then
       warden_print "Creating ZFS ${TDIR} dataset..."
       warden_run zfs create -o mountpoint="'/${tank}${zfsp}'" -p "'${tank}${zfsp}'"
       if [ $? -ne 0 ] ; then
         zfs destroy -fr "${tank}${zfsp}" >/dev/null 2>&1
         find "${tdir}"|xargs chflags noschg 
         rm -rf "${tdir}" >/dev/null 2>&1
         warden_exit "Failed creating ZFS base dataset"
       fi
    fi

    # Using a supplied tar file?
    if [ -n "$FBSDTAR" ] ; then
      local mtree_file
      local mtree_status=0
      local extract_status 
      local errmsg

      if [ -n "${MTREE}" ]; then
        mkdir -p "${JDIR}/.warden-files-cache/mtree"
        mtree_file="$(echo "${MTREE}"|sed -E 's|^.+/([^/]+$)|\1|')"
        mtree_file="${JDIR}/.warden-files-cache/mtree/${mtree_file}"

        if [ ! -s "${mtree_file}" ]; then
          warden_print "Getting mtree file ${MTREE}"
          warden_run fetch -o "${mtree_file}" "${MTREE}"
        fi
      fi 

      "${EXTRACT_TARBALL}" -u "${FBSDTAR}" -d "${TDIR}" -s "${EXTRACT_TARBALL_STATUSFILE}"
      extract_status=$?
      if [ "${extract_status}" != "0" ]; then
        errmsg="Failed extracting: $FBSDTAR"
      fi

      if [ -n "${MTREE}" ]; then
        mtree -f "${mtree_file}" -p "${TDIR}" > /tmp/.mtree.out
        mtree_status=$?
        if [ "${mtree_status}" != "0" ]; then
          errmsg="mtree failed for ${mtree_file}"
        fi

        grep -iq missing /tmp/.mtree.out
        if [ "$?" = "0" ]; then
          errmsg="missing files"
          mtree_status=1
        fi
      fi

      if [ "${extract_status}" != "0" -o "${mtree_status}" != "0" ] ; then
        zfs destroy -fr "${tank}${zfsp}"
        find "${tdir}"|xargs chflags noschg 
        rm -rf "${tdir}" >/dev/null 2>&1
        rm -rf /var/tmp/.extract
        warden_exit "${errmsg}"
      fi 

      rm -rf /var/tmp/.extract
      rm -f "${mtree_file}"

    elif [ "$oldFBSD" = "YES" ] ; then
      cd "${JDIR}/.download/"
      cat "${oldStr}".?? | tar --unlink -xpzf - -C "${TDIR}" 2>/dev/null
      cd "${JDIR}"

    elif [ "${TLINUXJAIL}" = "YES" -a -n "${LINUX_JAIL_SCRIPT}" ] ; then
      warden_print sh "${LINUX_JAIL_SCRIPT}" template_install "${TDIR}"
      sh "${LINUX_JAIL_SCRIPT}" template_install "${TDIR}" 2>&1 | warden_pipe
      sh "${LINUX_JAIL_SCRIPT}" error
      if [ $? -ne 0 ] ; then
         zfs destroy -fr "${tank}${zfsp}"
         find "${tdir}"|xargs chflags noschg 
         rm -rf "${tdir}" >/dev/null 2>&1
         warden_exit "Failed running ${LINUX_JAIL_SCRIPT}"
      fi

    else
      # Extract the dist files
      for f in $DFILES
      do
        tar xvpf "${DISTFILESDIR}/$f" -C "${TDIR}" 2>/dev/null
        if [ $? -ne 0 ] ; then
          zfs destroy -fr "${tank}${zfsp}"
          find "${tdir}"|xargs chflags noschg 
          rm -rf "${tdir}" >/dev/null 2>&1
          warden_exit "Failed extracting ZFS template environment"
        fi
        rm -f "${JDIR}/.download/${f}"
      done
    fi

    cp /etc/resolv.conf "${TDIR}/etc/resolv.conf"

    # Creating a plugin jail?
    if [ "$TPLUGJAIL" = "YES" ] ; then
      warden_print bootstrap_pkgng "${TDIR}" "pluginjail"
      bootstrap_pkgng "${TDIR}" "pluginjail"
      if [ $? -ne 0 ] ; then
        zfs destroy -fr "${tank}${zfsp}"
        find "${tdir}"|xargs chflags noschg 
        rm -rf "${tdir}" >/dev/null 2>&1
        warden_exit "Failed extracting ZFS template environment"
      fi
    fi

    warden_run zfs snapshot "'${tank}${zfsp}@clean'"
    if [ $? -ne 0 ] ; then
      warden_exit "Failed creating clean ZFS base snapshot"
    fi

    trap INT QUIT ABRT KILL TERM EXIT

  else
    TDIR="${JDIR}/.warden-template-${TNICK}"

    clean_exit()
    {
       find "${TDIR}" | xargs chflags noschg
       rm -rf "${TDIR}"
       warden_exit "Failed to create UFS template directory"
    }

    trap clean_exit INT QUIT ABRT KILL TERM EXIT

    # Sigh, still on UFS??
    if [ -d "${TDIR}" ]; then
       find "${TDIR}" | xargs chflags noschg
       rm -rf "${TDIR}"
    fi

    if [ -n "$FBSDTAR" ] ; then
      # User-supplied tar file 
      "${EXTRACT_TARBALL}" -u "${FBSDTAR}" -d "${TDIR}" -s "${EXTRACT_TARBALL_STATUSFILE}"

    elif [ "$oldFBSD" = "YES" ] ; then
      mkdir -p "${TDIR}"
      cd "${JDIR}/.download/"
      warden_print "Extrating FreeBSD..."
      cat "${oldStr}".?? | tar --unlink -xpzf - -C "${TDIR}" 2>/dev/null
      cd "${JDIR}"

      cp /etc/resolv.conf "${TDIR}/etc/resolv.conf"

      # Creating a plugin jail?
      if [ "$TPLUGJAIL" = "YES" ] ; then
        bootstrap_pkgng "${TDIR}/" "pluginjail"
      fi

      warden_print "Creating template archive..."
      tar cvjf "${TDIR}" -C "${TDIR}" 2>/dev/null
      find "${TDIR}"|xargs chflags noschg 
      rm -rf "${TDIR}"

    elif [ "${TLINUXJAIL}" = "YES" -a -n "${LINUX_JAIL_SCRIPT}" ] ; then
      warden_print sh "${LINUX_JAIL_SCRIPT}" template_install "${TDIR}"
      sh "${LINUX_JAIL_SCRIPT}" template_install "${TDIR}" 2>&1 | warden_pipe
      sh "${LINUX_JAIL_SCRIPT}" error
      if [ $? -ne 0 ] ; then
         find "${TDIR}"|xargs chflags noschg
         rm -rf "${TDIR}"
         warden_exit "Failed extracting UFS template environment"
      fi

    else
      # Extract the dist files
      mkdir -p "${TDIR}"
      for f in $DFILES
      do
        tar xvpf "${DISTFILESDIR}/$f" -C "${TDIR}" 2>/dev/null
        if [ $? -ne 0 ] ; then 
           find "${TDIR}"|xargs chflags noschg
           rm -rf "${TDIR}"
           warden_exit "Failed extracting UFS template environment"
        fi
        rm -f "${JDIR}/.download/${f}"
      done

      cp /etc/resolv.conf "${TDIR}/etc/resolv.conf"

      # Creating a plugin jail?
      if [ "$TPLUGJAIL" = "YES" ] ; then
        bootstrap_pkgng "${TDIR}/" "pluginjail"
      fi

      warden_print "Creating template archive..."
      tar -cvjf - -C "${TDIR}" > "${TDIR}" 2>/dev/null
      find "${TDIR}"|xargs chflags noschg
      rm -rf "${TDIR}"
    fi
  fi

  trap INT QUIT ABRT KILL TERM EXIT

  rm -rf "${JDIR}/.download"
  warden_print "Created jail template: $TNICK"
  exit 0
};

ifs="${IFS}"
IFS=$'\n'

# Read our flags
while [ $# -gt 0 ]; do
   case "$1" in
    -fbsd) shift
           if [ -z "$1" ] ; then warden_exit "No FreeBSD version specified"; fi
           FBSDVER="${1}"
           ;;
  -trueos) shift
           if [ -z "$1" ] ; then warden_exit "No TrueOS version specified"; fi
           TRUEOSVER="${1}"
           ;;
    -arch) shift
           if [ -z "$1" ] ; then warden_exit "No FreeBSD architecture specified"; fi
           FBSDARCH="${1}"
           ;;
    -tar) shift
           if [ -z "$1" ] ; then warden_exit "No tar file specified"; fi
           if [ ! -e "$1" ] ; then
              echo "$1" | egrep -iq '^(http|https|ftp)://'
              if [ "$?" != "0" ] ; then warden_exit "Could not find tar file: $1"; fi
           fi
           FBSDTAR="${1}"
           ;;
    -nick) shift
           if [ -z "$1" ] ; then warden_exit "No nickname specified"; fi
           TNICK="${1}"
	   ;;
 -pluginjail) shift
           TPLUGJAIL="YES"
	   ;;
  -linuxjail) shift
           TLINUXJAIL="YES"
	   ;;
  -mtree) shift
           MTREE="${1}"
	   ;;
	*) warden_exit "Invalid option: $1" ;;
   esac
   shift
done

IFS="${ifs}"

if [ -z "$TNICK" ] ; then
  warden_exit "No nickname specified, use -nick <nickname>"
fi

if [ -z "$FBSDTAR" ] ; then 
  if [ -z "$FBSDVER" -a -z "${TRUEOSVER}" ] ; then
    warden_exit "Need either -fbsd or -trueos specified!"
  fi
  case $FBSDARCH in
  amd64) if [ "`uname -m`" != "amd64" ] ; then
           warden_exit "Can only use amd64 on amd64 systems";
         fi
         ;;
   i386) ;;
      *) warden_exit "Arch needs to be amd64 or i386" ;;
  esac
fi

# Set the template directory
TDIR="${JDIR}/.warden-template-$TNICK"
export TDIR

DISTFILES="distfiles/${FBSDVER}/${FBSDARCH}"
PACKAGES="packages/${FBSDVER}/${FBSDARCH}"

DISTFILESDIR="${CACHEDIR}/${DISTFILES}"
PACKAGESDIR="${CACHEDIR}/${PACKAGES}"
export DISTFILESDIR PACKAGESDIR

if [ ! -d "${DISTFILESDIR}" ]
then
  mkdir -p "${DISTFILESDIR}"
fi
if [ ! -d "${PACKAGESDIR}" ]
then
  mkdir -p "${PACKAGESDIR}"
fi

if [ -d "${PROGDIR}/${DISTFILES}" ] ; then
  diff -urN "${PROGDIR}/${DISTFILES}/" "${DISTFILESDIR}/" >/dev/null 2>&1
  if [ "$?" != "0" ] ; then
    cp "${PROGDIR}/${DISTFILES}"/* "${DISTFILESDIR}/"
  fi
fi
if [ -d "${PROGDIR}/${PACKAGES}" ] ; then
  diff -urN "${PROGDIR}/${PACKAGES}/" "${PACKAGESDIR}/" >/dev/null 2>&1
  if [ "$?" != "0" ] ; then
    cp "${PROGDIR}/${PACKAGES}"/* "${PACKAGESDIR}/"
  fi
fi

# Set the name based upon if using ZFS or UFS
isDirZFS "${JDIR}"
if [ $? -eq 0 ] ; then
  TDIR="${TDIR}"
else
  TDIR="${TDIR}.tbz"
fi

# Make sure this template is available
if [ -e "${TDIR}" ] ; then 
  warden_exit "A template with this nickname already exists!"
fi

# Set the files we will be downloading
DFILES="base.txz doc.txz games.txz"
if [ "$FBSDARCH" = "amd64" ] ; then
  DFILES="$DFILES lib32.txz"
fi

TOTAL_INSTALL_FILES=$(echo $DFILES|wc|awk '{ print $2 }')

if [ "${VANILLA}" != "NO" ] ; then
  n="$(wc -l ${PROGDIR}/pcbsd-utils-packages|awk '{ print $1 }')"
  : $(( TOTAL_INSTALL_FILES += n ))
fi

if [ "${TPLUGJAIL}" = "YES" ] ; then
  n="$(wc -l ${PROGDIR}/pluginjail-packages|awk '{ print $1 }')"
  : $(( TOTAL_INSTALL_FILES += n ))
fi

# pkg.txz and repo.txz
if [ "${VANILLA}" != "NO" -o "${TPLUGJAIL}" = "YES" ] ; then
  : $(( TOTAL_INSTALL_FILES += 2 ))
fi

export TOTAL_INSTALL_FILES

# Check if we are on REAL old versions of FreeBSD
if [ -n "$FBSDVER" ] ; then
  mV=`echo $FBSDVER | cut -d '.' -f 1`
  if [ $mV -lt 9 ] ; then 
     oldFBSD="YES"
     oldStr="base"
  fi
  if [ $mV -lt 5 ] ; then 
     # VERY VERY old!
     oldFBSD="YES"
     oldStr="bin"
  fi
fi

# This is a Linux jail and a tar file has been specified
if [ "${TLINUXJAIL}" = "YES" -a -z "${LINUX_JAIL_SCRIPT}" -a -n "${FBSDTAR}" ] ; then
  # Do nothing?
  :

# This is a Linux jail with no tar file
elif [ "${TLINUXJAIL}" = "YES" -a -n "${LINUX_JAIL_SCRIPT}" ] ; then
  warden_print sh "${LINUX_JAIL_SCRIPT}" get_distfiles "${TDIR}"
  sh "${LINUX_JAIL_SCRIPT}" get_distfiles "${TDIR}" 2>&1 | warden_pipe

# If not using a tarball, lets download our files
elif [ -z "$FBSDTAR" ] ; then
  download_template_files
fi

# Create the template now
create_template

exit 0
