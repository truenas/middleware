#!/bin/sh
#
# See README for up to date usage examples.
# vim: syntax=sh noexpandtab
#

umask 022
cd "$(dirname "$0")/.."
TOP="$(pwd)"

. build/nano_env
. build/functions.sh

check_build_sanity()
{
    # The build will fail if we make directories too long due to
    # using nullfs.  This is because nullfs can not handle long
    # directory names for mounts.
    # Catch this early so we don't spend a lot of time doing stuff
    # just to get a build error.
    local mypwd=`pwd`
    local mypwdlen=`pwd | wc -c | awk '{print $1}'`  # use awk to cleanup wc output
    local pwdmaxlen="38"
    if [ $mypwdlen -ge $pwdmaxlen ] ; then
        cat <<PWD_ERROR
=================================================================
FATAL:
current path (pwd) too long ($mypwdlen) for nullfs mounts during
build.
=================================================================
WHY:
Building ports will very likely fail when doing nullfs.
=================================================================
TO FIX:
please rename/move your build directory to a place with a shorter
less than $pwdmaxlen characters)
current pwd: '$mypwd'
PWD_ERROR
        exit 1
    fi
}

check_for_command_from_port()
{
   local COMMAND=$1
   local PACKAGE=$2
   local FOUND
   local MSG

   FOUND="$(command -v $COMMAND || echo '')"

   if [ -z "$FOUND" ]; then
       MSG="ERROR: $COMMAND not found."
       if [ -n "$PACKAGE" ]; then
           MSG="$MSG.\nERROR: Please run 'pkg install $PACKAGE' or install from ports."
       fi
       printf "\n$MSG\n\n"
       exit 1
   fi 
}

check_for_pylib_from_port()
{
   local LIB=$1
   local PACKAGE=$2
   local FOUND
   local MSG
   local PYPATH="/usr/local/lib/python2.7/site-packages"

   FOUND="$(ls $PYPATH/$LIB.py || echo '')"

   if [ -z "$FOUND" ]; then
       MSG="ERROR: Python 2.7 site package $LIB not found."
       if [ -n "$PACKAGE" ]; then
           MSG="$MSG.\nERROR: Please run 'pkg install $PACKAGE' or install from ports."
       fi
       printf "\n$MSG\n\n"
       exit 1
   fi 
}

check_build_tools()
{
	check_for_command_from_port git devel/git
	check_for_command_from_port pxz archivers/pxz
	check_for_command_from_port xz archivers/xz
	check_for_command_from_port python lang/python
	check_for_command_from_port python2 lang/python2
	check_for_command_from_port poudriere ports-mgmt/poudriere-devel
	check_for_command_from_port grub-mkrescue sysutils/grub2-pcbsd
	check_for_command_from_port xorriso sysutils/xorriso
	check_for_command_from_port sphinx-build textproc/py-sphinx
	check_for_pylib_from_port sphinxcontrib/httpdomain textproc/py-sphinxcontrib-httpdomain
}

main()
{
	#
	# Do extra checks to make sure the build will succeed.
	#
	check_build_sanity

	check_build_tools
}


main "$@"
