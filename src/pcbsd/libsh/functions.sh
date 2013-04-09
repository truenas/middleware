#!/bin/sh
# Functions we can source for pc-bsd scripts
# Author: Kris Moore
# Copyright: 2012
# License: BSD
##############################################################

PCBSD_ETCCONF="/usr/local/etc/pcbsd.conf"

download_cache_packages()
{
  if [ ! -e "/usr/local/etc/pkg.conf" ] ; then
    exit_err "No /usr/local/etc/pkg.conf!"
  fi

  # Tickle pkg update first
  pkg-static update
  local ARCH="`uname -m`"

  ${1} > /tmp/.pkgUpList.$$

  while read line
  do
     lTag=`echo $line | awk '{print $1}'` 
     case $lTag in
    Upgrading|Downgrading) pkgList="`echo $line | awk '{print $2}' | sed 's|:||g'`-`echo $line | awk '{print $5}'`.txz $pkgList" ;;
 Reinstalling) pkgList="`echo $line | awk '{print $2}'`.txz $pkgList" ;;
   Installing) pkgList="`echo $line | awk '{print $2}' | sed 's|:||g'`-`echo $line | awk '{print $3}'`.txz $pkgList" ;;
                    *) continue ;;
     esac

  done < /tmp/.pkgUpList.$$
  rm /tmp/.pkgUpList.$$

  # Get the PKG_CACHEDIR
  PKG_CACHEDIR="/var/cache/pkg"
  cat /usr/local/etc/pkg.conf | grep -q "^PKG_CACHEDIR:"
  if [ $? -eq 0 ] ; then
    PKG_CACHEDIR="`grep '^PKG_CACHEDIR:' /usr/local/etc/pkg.conf | awk '{print $2}'`"
  fi
  if [ -z "$PKG_CACHEDIR" ] ; then
     exit_err "Failed getting PKG_CACHEDIR"
  fi
  export PKG_CACHEDIR

  # Where are the packages on our mirrors?
  pkgUrl="/packages/`uname -r`/${ARCH}"

  if [ ! -d "$PKG_CACHEDIR/All" ] ; then
     mkdir -p ${PKG_CACHEDIR}/All
  fi

  for i in $pkgList
  do
    if [ -e "${PKG_CACHEDIR}/All/${i}" ] ; then rm ${PKG_CACHEDIR}/All/${i} ; fi
    get_file_from_mirrors "${pkgUrl}/All/${i}" "${PKG_CACHEDIR}/All/${i}"
    if [ $? -ne 0 ] ; then
      exit_err "Failed downloading: /${pkgUrl}/All/${i}"
    fi
  done
}

get_mirror() {

  # Check if we already looked up a mirror we can keep using
  if [ -n "$CACHED_PCBSD_MIRROR" ] ; then
     VAL="$CACHED_PCBSD_MIRROR"
     export VAL
     return
  fi

  # Set the mirror URL
  VAL="`cat ${PCBSD_ETCCONF} 2>/dev/null | grep 'PCBSD_MIRROR: ' | sed 's|PCBSD_MIRROR: ||g'`"
  if [ -n "$VAL" ] ; then
     echo "Using mirror: $VAL"
     CACHED_PCBSD_MIRROR="$VAL"
     export VAL CACHED_PCBSD_MIRROR
     return
  fi

  echo "Getting regional mirror..."
  . /etc/profile

  # No URL? Lets get one from the master server
  local mFile="${HOME}/.mirrorUrl.$$"
  touch $mFile
  fetch -o $mFile http://getmirror.pcbsd.org >/dev/null 2>/dev/null
  VAL="`cat $mFile | grep 'URL: ' | sed 's|URL: ||g'`"
  rm $mFile
  if [ -n "$VAL" ] ; then
     echo "Using mirror: $VAL"
     CACHED_PCBSD_MIRROR="$VAL"
     export VAL CACHED_PCBSD_MIRROR
     return
  fi

  # Still no mirror? Lets try the PC-BSD FTP server...
  VAL="ftp://ftp.pcbsd.org/pub/mirror"
  CACHED_PCBSD_MIRROR="$VAL"
  export VAL CACHED_PCBSD_MIRROR
  echo "Using mirror: $VAL"
  return 
}

# Function which returns the installed list of PC-BSD mirrors for use
# with the aria2c command
# Will return just a single mirror, if the user has manually specified one
# in /usr/local/etc/pcbsd.conf
get_aria_mirror_list()
{
  if [ -z $1 ] ; then
     exit_err "Need to supply file to grab from mirrors..."
  fi

  # Set the mirror URL
  local VAL="`cat ${PCBSD_ETCCONF} 2>/dev/null | grep 'PCBSD_MIRROR: ' | sed 's|PCBSD_MIRROR: ||g'`"
  if [ -n "$VAL" ] ; then
     echo "${VAL}${1}"
     return
  fi

  if [ ! -e "/usr/local/share/pcbsd/conf/pcbsd-mirrors" ] ; then
     exit_err "Missing mirror list: /usr/local/share/pcbsd/conf/pcbsd-mirrors"
  fi

  # Build the mirror list
  while read line
  do
    VAL="$VAL ${line}${1}"
  done < /usr/local/share/pcbsd/conf/pcbsd-mirrors
  echo ${VAL}
}

# Function to download a file from the pcbsd mirrors
# Arg1 = Remote File URL
# Arg2 = Where to save file
get_file_from_mirrors()
{
   _rf="${1}"
   _lf="${2}"

   # Get any proxy information
   . /etc/profile

   # Split up the dir / file name
   local aDir=`dirname $_lf`
   local aFile=`basename $_lf`

   # Server status flag
   local aStatFile=${HOME}/.pcbsd-aria-stat
   if [ -e "$aStatFile" ] ; then
     local aStat="--server-stat-of=$aStatFile --server-stat-if=$aStatFile --uri-selector=adaptive --server-stat-timeout=864000"
   else
     local aStat="--server-stat-of=$aStatFile --uri-selector=adaptive"
   fi
   touch $aStatFile

   # Get mirror list
   local mirrorList="$(get_aria_mirror_list $1)"
   
   # Running from a non GUI?
   if [ "$GUI_FETCH_PARSING" != "YES" -a "$PBI_FETCH_PARSING" != "YES" -a -z "$PCFETCHGUI" ] ; then
      aria2c -k 5M ${aStat} --check-certificate=false --file-allocation=none -d "${aDir}" -o "${aFile}" ${mirrorList}
      return $?
   fi

   echo "FETCH: ${_rf}"

   # Doing a front-end download, parse the output of fetch
   _eFile="/tmp/.fetch-exit.$$"
   fetch -s "`echo ${mirrorList} | awk '{print $1}'`" > /tmp/.fetch-size.$$ 2>/dev/null
   _fSize=`cat /tmp/.fetch-size.$$ 2>/dev/null`
   _fSize="`expr ${_fSize} / 1024 2>/dev/null`"
   rm "/tmp/.fetch-size.$$" 2>/dev/null
   _time=1

   ( aria2c -o ${aFile} -d ${aDir} -k 5M ${aStat} --check-certificate=false --file-allocation=none ${mirrorList} >/dev/null 2>/dev/null ; echo "$?" > ${_eFile} ) &
   FETCH_PID=`ps -auwwwx | grep -v grep | grep "aria2c -o ${aFile}" | awk '{print $2}'`
   while : 
   do
      if [ -e "${_lf}" ] ; then
         _dSize=`du -k ${_lf} | tr -d '\t' | cut -d '/' -f 1`
         if [ $(is_num "$_dSize") ] ; then
            if [ ${_fSize} -lt ${_dSize} ] ; then _dSize="$_fSize" ; fi
	    _kbs=`expr ${_dSize} \/ $_time`
	    echo "SIZE: ${_fSize} DOWNLOADED: ${_dSize} SPEED: ${_kbs} KB/s"
  	 fi
      fi

      # Make sure download isn't finished
      ps -p $FETCH_PID >/dev/null 2>/dev/null
      if [ "$?" != "0" ] ; then break ; fi
      sleep 2
      _time=`expr $_time + 2`
   done

   _err="`cat ${_eFile}`"
   rm ${_eFile} 2>/dev/null
   if [ "$_err" = "0" ]; then echo "FETCHDONE" ; fi
   unset FETCH_PID
   return $_err

}

# Function to download a file from remote using fetch
# Arg1 = Remote File URL
# Arg2 = Where to save file
# Arg3 = Number of attempts to make before failing
get_file() {

	_rf="${1}"
	_lf="${2}"
        _ftries=${3}
	if [ -z "$_ftries" ] ; then _ftries=3; fi

        # Get any proxy information
        . /etc/profile

	if [ -e "${_lf}" ] ; then 
		echo "Resuming download of: ${_lf}"
	fi

	if [ "$GUI_FETCH_PARSING" != "YES" -a -z "$PCFETCHGUI" ] ; then
		fetch -r -o "${_lf}" "${_rf}"
		_err=$?
	else
		echo "FETCH: ${_rf}"

		# Doing a front-end download, parse the output of fetch
		_eFile="/tmp/.fetch-exit.$$"
		fetch -s "${_rf}" > /tmp/.fetch-size.$$ 2>/dev/null
		_fSize=`cat /tmp/.fetch-size.$$ 2>/dev/null`
		_fSize="`expr ${_fSize} / 1024 2>/dev/null`"
		rm "/tmp/.fetch-size.$$" 2>/dev/null
		_time=1

		( fetch -r -o "${_lf}" "${_rf}" >/dev/null 2>/dev/null ; echo "$?" > ${_eFile} ) &
		FETCH_PID=`ps -auwwwx | grep -v grep | grep "fetch -r -o ${_lf}" | awk '{print $2}'`
		while : 
		do
			if [ -e "${_lf}" ] ; then
				_dSize=`du -k ${_lf} | tr -d '\t' | cut -d '/' -f 1`
				if [ $(is_num "$_dSize") ] ; then
					if [ ${_fSize} -lt ${_dSize} ] ; then _dSize="$_fSize" ; fi
					_kbs=`expr ${_dSize} \/ $_time`
					echo "SIZE: ${_fSize} DOWNLOADED: ${_dSize} SPEED: ${_kbs} KB/s"
				fi
			fi

			# Make sure download isn't finished
			ps -p $FETCH_PID >/dev/null 2>/dev/null
			if [ "$?" != "0" ] ; then break ; fi
			sleep 2
			_time=`expr $_time + 2`
		done

		_err="`cat ${_eFile}`"
                rm ${_eFile} 2>/dev/null
		if [ "$_err" = "0" ]; then echo "FETCHDONE" ; fi
		unset FETCH_PID
	fi

	echo ""
	if [ $_err -ne 0 -a $_ftries -gt 0 ] ; then
		sleep 30
		_ftries=`expr $_ftries - 1`

		# Remove the local file if we failed
		if [ -e "${_lf}" ]; then rm "${_lf}"; fi

		get_file "${_rf}" "${_lf}" $_ftries	
		_err=$?
	fi
	return $_err
}

# Check if a value is a number
is_num()
{
        expr $1 + 1 2>/dev/null
        return $?
}

# Exit with a error message
exit_err() {
	if [ -n "${LOGFILE}" ] ; then
           echo "ERROR: $*" >> ${LOGFILE}
	fi
  	echo >&2 "ERROR: $*"
        exit 1
}


### Print an error on STDERR and bail out
printerror() {
  exit_err $*
}


# Check if the target directory is on ZFS
# Arg1 = The dir to check
# Arg2 = If set to 1, don't dig down to lower level directory
isDirZFS() {
  local _chkDir="$1"
  while :
  do
     # Is this dir a ZFS mount
     mount | grep -w "on $_chkDir " | grep -qw "(zfs," && return 0

     # If this directory is mounted, but NOT ZFS
     if [ "$2" != "1" ] ; then
       mount | grep -qw "on $_chkDir " && return 1
     fi
      
     # Quit if not walking down
     if [ "$2" = "1" ] ; then return 1 ; fi
  
     if [ "$_chkDir" = "/" ] ; then break ; fi
     _chkDir=`dirname $_chkDir`
  done
  
  return 1
}

# Gets the mount-point of a particular zpool / dataset
# Arg1 = zpool to check
getZFSMount() {
  local zpool="$1"
  local mnt=`mount | grep "^${zpool} on" | grep "(zfs," | awk '{print $3}'`
  if [ -n "$mnt" ] ; then
     echo "$mnt"
     return 0
  fi
  return 1
}

# Get the ZFS dataset of a particular directory
getZFSDataset() {
  local _chkDir="$1"
  while :
  do
    local zData=`mount | grep " on ${_chkDir} " | grep "(zfs," | awk '{print $1}'`
    if [ -n "$zData" ] ; then
       echo "$zData"
       return 0
    fi
    if [ "$2" != "rec" ] ; then return 1 ; fi
    if [ "$_chkDir" = "/" ] ; then return 1 ; fi
    _chkDir=`dirname $_chkDir`
  done
  return 1
}

# Get the ZFS tank name for a directory
# Arg1 = Directory to check
getZFSTank() {
  local _chkDir="$1"
  while :
  do
     line=`mount | grep -we "$_chkDir" | grep -e "(zfs,"`
     mount | grep -we "$_chkDir" | grep -q -e "(zfs,"
     if [ $? -eq 0 ] ; then
        echo $line | cut -d '/' -f -1 | awk '{print $1}'
        return 0
     fi

     if [ "$_chkDir" = "/" ] ; then return 1 ; fi
     _chkDir=`dirname $_chkDir`
  done

  return 1
}

# Get the mountpoint for a ZFS name
# Arg1 = name
getZFSMountpoint() {
   local _chkName="${1}"
   if [ -z "${_chkName}" ]; then return 1 ; fi

   zfs list "${_chkName}" | tail -1 | awk '{ print $5 }'
}

# Get the ZFS relative path for a path
# Arg1 = Path
getZFSRelativePath() {
   local _chkDir="${1}"
   local _tank=`getZFSTank "$_chkDir"`
   local _mp=`getZFSMountpoint "${_tank}"`

   if [ -z "${_tank}" ] ; then return 1 ; fi

   local _name="${_chkDir#${_mp}}"
   echo "${_name}"
   return 0
}

# Check if an address is IPv6
isV6() {
  echo ${1} | grep -q ":"
  return $?
}
    
# Is a mount point, or any of its parent directories, a symlink?
is_symlinked_mountpoint()
{
        local _dir
        _dir=$1
        [ -L "$_dir" ] && return 0
        [ "$_dir" = "/" ] && return 1
        is_symlinked_mountpoint `dirname $_dir`
        return $?
}

# Function to ask the user to press Return to continue
rtn()
{
  echo -e "Press ENTER to continue\c";
  read garbage
};

# Function to check if an IP address passes a basic sanity test
check_ip()
{
  ip="$1"
  
  # If this is a V6 address, skip validation for now
  isV6 "${ip}"
  if [ $? -eq 0 ] ; then return ; fi

  # Check if we can cut this IP into the right segments 
  SEG="`echo $ip | cut -d '.' -f 1 2>/dev/null`"
  echo $SEG | grep -E "^[0-9]+$" >/dev/null 2>/dev/null
  if [ "$?" != "0" ]
  then
     return 1
  fi
  if [ $SEG -gt 255 -o $SEG -lt 0 ]
  then
     return 1
  fi
  
  # Second segment
  SEG="`echo $ip | cut -d '.' -f 2 2>/dev/null`"
  echo $SEG | grep -E "^[0-9]+$" >/dev/null 2>/dev/null
  if [ "$?" != "0" ]
  then
     return 1
  fi
  if [ $SEG -gt 255 -o $SEG -lt 0 ]
  then
     return 1
  fi

  # Third segment
  SEG="`echo $ip | cut -d '.' -f 3 2>/dev/null`"
  echo $SEG | grep -E "^[0-9]+$" >/dev/null 2>/dev/null
  if [ "$?" != "0" ]
  then
     return 1
  fi
  if [ $SEG -gt 255 -o $SEG -lt 0 ]
  then
     return 1
  fi
  
  # Fourth segment
  SEG="`echo $ip | cut -d '.' -f 4 2>/dev/null`"
  echo $SEG | grep -E "^[0-9]+$" >/dev/null 2>/dev/null
  if [ "$?" != "0" ]
  then
     return 1
  fi
  if [ $SEG -gt 255 -o $SEG -lt 0 ]
  then
     return 1
  fi

  return 0
};
