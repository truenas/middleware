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
  if [ -d "${JDIR}/.download" ] ; then rm -rf ${JDIR}/.download; fi
  mkdir ${JDIR}/.download

  if [ ! -d "${JDIR}" ] ; then mkdir -p "${JDIR}" ; fi
  cd ${JDIR}

  warden_print "Fetching jail environment. This may take a while..."
  if [ -n "$TRUEOSVER" ] ; then
     for f in $DFILES
     do
       get_file_from_mirrors "/${TRUEOSVER}/${FBSDARCH}/dist/$f" "${JDIR}/.download/$f"
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
	 done < ${JDIR}/.download/${oldStr}.inf
	 return
     fi

     for f in $DFILES
     do
       warden_run fetch -o "${JDIR}/.download/$f" "ftp://ftp.freebsd.org/pub/FreeBSD/releases/${FBSDARCH}/${FBSDVER}/$f"
       if [ $? -ne 0 ] ; then
	 warden_print "Trying ftp-archive..."
         warden_run fetch -o "${JDIR}/.download/$f" "http://ftp-archive.freebsd.org/pub/FreeBSD-Archive/old-releases/${FBSDARCH}/${FBSDVER}/$f"
         if [ $? -ne 0 ] ; then
           warden_exit "Failed downloading: FreeBSD ${FBSDVER}"
	 fi
       fi
     done
  fi
}

create_template()
{
  # Creating ZFS dataset?
  isDirZFS "${JDIR}"
  if [ $? -eq 0 ] ; then
    local zfsp=`getZFSRelativePath "${TDIR}"`

    # Use ZFS base for cloning
    tank=`getZFSTank "${JDIR}"`

    mnt=`getZFSMountpoint ${tank}`
    tdir="${mnt}${zfsp}"

    clean_exit()
    {
       cd /
       zfs destroy -fR "${tank}${zfsp}"
       rm -rf "${tdir}" >/dev/null 2>&1
       warden_exit "Failed to create ZFS base dataset"
    }

    trap clean_exit INT QUIT ABRT KILL TERM EXIT

    isDirZFS "${TDIR}" "1"
    if [ $? -ne 0 ] ; then
       warden_print "Creating ZFS ${TDIR} dataset..."
       warden_run zfs create -o mountpoint=/${tank}${zfsp} -p ${tank}${zfsp}
       if [ $? -ne 0 ] ; then
         zfs destroy -fR "${tank}${zfsp}" >/dev/null 2>&1
         rm -rf "${tdir}" >/dev/null 2>&1
         warden_exit "Failed creating ZFS base dataset"
       fi
    fi

    # Using a supplied tar file?
    if [ -n "$FBSDTAR" ] ; then
      tar xvpf $FBSDTAR -C ${TDIR} 2>/dev/null
      if [ $? -ne 0 ] ; then
        zfs destroy -fR "${tank}${zfsp}"
        rm -rf "${tdir}" >/dev/null 2>&1
        warden_exit "Failed extracting: $FBSDTAR"
      fi

    elif [ "$oldFBSD" = "YES" ] ; then
      cd ${JDIR}/.download/
      cat ${oldStr}.?? | tar --unlink -xpzf - -C ${TDIR} 2>/dev/null
      cd ${JDIR}

    else
      # Extract the dist files
      for f in $DFILES
      do
        tar xvpf ${JDIR}/.download/$f -C ${TDIR} 2>/dev/null
        if [ $? -ne 0 ] ; then
          zfs destroy -fR "${tank}${zfsp}"
          rm -rf "${tdir}" >/dev/null 2>&1
          warden_exit "Failed extracting ZFS template environment"
        fi
        rm ${JDIR}/.download/${f}
      done
    fi

    # Creating a plugin jail?
    if [ "$TPLUGJAIL" = "YES" ] ; then
      cp /etc/resolv.conf ${TDIR}/etc/resolv.conf

      warden_print bootstrap_pkgng "${TDIR}" "pluginjail"
      bootstrap_pkgng "${TDIR}" "pluginjail"
      if [ $? -ne 0 ] ; then
        zfs destroy -fR "${tank}${zfsp}"
        rm -rf "${tdir}" >/dev/null 2>&1
        warden_exit "Failed extracting ZFS template environment"
      fi
    fi

    warden_run zfs snapshot ${tank}${zfsp}@clean
    if [ $? -ne 0 ] ; then
      warden_exit "Failed creating clean ZFS base snapshot"
    fi

    trap INT QUIT ABRT KILL TERM EXIT

  else
    # Sigh, still on UFS??
    if [ -d "${JDIR}/.templatedir" ]; then
       rm -rf ${JDIR}/.templatedir
    fi

    if [ -n "$FBSDTAR" ] ; then
      # User-supplied tar file 
      cp $FBSDTAR ${TDIR}
    elif [ "$oldFBSD" = "YES" ] ; then
      mkdir ${JDIR}/.templatedir
      cd ${JDIR}/.download/
      warden_print "Extrating FreeBSD..."
      cat ${oldStr}.?? | tar --unlink -xpzf - -C ${JDIR}/.templatedir 2>/dev/null
      cd ${JDIR}

      # Creating a plugin jail?
      if [ "$TPLUGJAIL" = "YES" ] ; then
        cp /etc/resolv.conf ${JDIR}/.templatedir/etc/resolv.conf
        bootstrap_pkgng "${JDIR}/.templatedir/" "pluginjail"
      fi

      warden_print "Creating template archive..."
      tar cvjf ${TDIR} -C ${JDIR}/.templatedir 2>/dev/null
      rm -rf ${JDIR}/.templatedir
    else
      # Extract the dist files
      mkdir ${JDIR}/.templatedir
      for f in $DFILES
      do
        tar xvpf ${JDIR}/.download/$f -C ${JDIR}/.templatedir 2>/dev/null
        if [ $? -ne 0 ] ; then 
           rm -rf ${JDIR}/.templatedir
           warden_exit "Failed extracting ZFS template environment"
        fi
        rm ${JDIR}/.download/${f}
      done

      # Creating a plugin jail?
      if [ "$TPLUGJAIL" = "YES" ] ; then
        cp /etc/resolv.conf ${JDIR}/.templatedir/etc/resolv.conf
        bootstrap_pkgng "${JDIR}/.templatedir/" "pluginjail"
      fi

      warden_print "Creating template archive..."
      tar cvjf ${TDIR} -C ${JDIR}/.templatedir 2>/dev/null
      rm -rf ${JDIR}/.templatedir
    fi
  fi

  rm -rf ${JDIR}/.download
  warden_print "Created jail template: $TNICK"
  exit 0
};


# Read our flags
while [ $# -gt 0 ]; do
   case $1 in
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
           if [ ! -e "$1" ] ; then warden_exit "Could not find tar file: $1"; fi
           FBSDTAR="${1}"
           ;;
    -nick) shift
           if [ -z "$1" ] ; then warden_exit "No nickname specified"; fi
           TNICK="${1}"
	   ;;
 -pluginjail) shift
           TPLUGJAIL="YES"
	   ;;
	*) warden_exit "Invalid option: $1" ;;
   esac
   shift
done

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

# If not using a tarball, lets download our files
if [ -z "$FBSDTAR" ] ; then
  download_template_files
fi

# Create the template now
create_template

exit 0
