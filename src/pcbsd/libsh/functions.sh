#!/bin/sh
# Functions we can source for pc-bsd scripts
# Author: Kris Moore
# Copyright: 2012
# License: BSD
##############################################################

PCBSD_ETCCONF="/usr/local/etc/pcbsd.conf"

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
      
     # Quit if not walking down
     if [ "$2" = "1" ] ; then return 1 ; fi
  
     if [ "$_chkDir" = "/" ] ; then break ; fi
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
     line=`mount | grep -w -e $_chkDir -e "(zfs,"`
     mount | grep -qw -e $_chkDir -e "(zfs,"
     if [ $? -eq 0 ] ; then
        echo $line | cut -d '/' -f -1 | awk '{print $1}'
        return 0
     fi

     if [ "$_chkDir" = "/" ] ; then return 1 ; fi
     _chkDir=`dirname $_chkDir`
  done

  return 1
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
