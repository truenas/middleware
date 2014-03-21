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

# Number of jobs to pass to make. Only applies to src so far.
MAKE_JOBS=$(( 2 * $(sysctl -n kern.smp.cpus) + 1 ))
if [ ${MAKE_JOBS} -gt 10 ]; then
	MAKE_JOBS=10
fi
export MAKE_JOBS

# Available targets to build
BUILD_TARGETS="os-base"

# Targets to build (os-base, plugins/<plugin>).
TARGETS=""

# Trace flags
TRACE=""

# NanoBSD flags
NANO_ARGS=""

usage() {
	cat <<EOF
usage: ${0##*/} [-afJsx] [-j make-jobs] [-t target1] [-t target2] [ -t ...] [-- nanobsd-options]

-a		- Build all targets
-j make-jobs	- number of make jobs to run; defaults to ${MAKE_JOBS}.
-s		- show build targets
-t target	- target to build (os-base, <plugin-name>, etc).
		  This switch can be used more than once to specify multiple targets.
-x		- enable sh -x debugging
-z		- End script before images are built.  This is useful for
		  preloading a package build so you can do a full build after this
		  and compress the resulting thin image.

EOF
	exit 1
}

check_build_sanity()
{
    # The build will fail if we make directories too long due to
    # using nullfs.  This is because nullfs can not handle long
    # directory names for mounts.
    # Catch this early so we don't spend a lot of time doing stuff
    # just to get a build error.
    local mypwd=`pwd`
    local mypwdlen=`pwd | wc -c | awk '{print $1}'`  # use awk to cleanup wc output
    local pwdmaxlen="45"
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

show_build_targets()
{
	for _target in ${BUILD_TARGETS}
	do
		echo "${_target}"
	done
	exit 1
}

parse_cmdline()
{
	while getopts 'afj:st:xz' _optch
	do
		case "${_optch}" in
		a)
			TARGETS="${BUILD_TARGETS}"
			;;
		j)
			echo ${OPTARG} | egrep -q '^[[:digit:]]+$' && [ ${OPTARG} -gt 0 ]
			if [ $? -ne 0 ]; then
				usage
			fi
			MAKE_JOBS=${OPTARG}
			;;
		s)	
			show_build_targets
			;;
		t)
			TARGETS="${TARGETS} ${OPTARG}"
			;;
		x)
			TRACE="-x"
			;;
		z)
			export PACKAGE_PREP_BUILD=1
			;;
		\?)
			usage
			;;
		esac
	done

	shift $((${OPTIND} - 1))

	NANO_ARGS="$@"
	export NANO_ARGS
}

expand_targets()
{
	local _targets=""
	for _target in ${TARGETS}
	do
		if [ -f "${NANO_CFG_BASE}/${_target}" ]
		then
			_targets="${_targets} ${NANO_CFG_BASE}/${_target}"
		fi
	done
	TARGETS="${_targets}"

	if [ -z "${TARGETS}" ]
	then
		error "Build targets -- ${TARGETS} -- don't exist"
	fi
}

build_target()
{
	local _target="${1}"
	local _args="${NANO_ARGS}"
	local _nanobsd="${AVATAR_ROOT}/build/nanobsd/nanobsd.sh"
	local _c

	export AVATAR_COMPONENT=${_target##*/}

	#
	# XXX: chicken and egg problem. Not doing this will always cause plugins-base,
	# etc to rebuild if os-base isn't already present, or the build to fail if
	# os-base is built and plugins-base isn't, etc.
	#
	export NANO_OBJ=${AVATAR_ROOT}/${AVATAR_COMPONENT}/${NANO_ARCH}

	local _required_logs="_.iw"
	if [ "${AVATAR_COMPONENT}" = "os-base" ]
	then
		#
		# The base OS distro requires a kernel build.
		#
		_required_logs="_.ik _.iw"
	fi

	_c=$(echo ${AVATAR_COMPONENT} | tr '-' '_')
		
	export "${_c}_FORCE=1"

	local _cmd="${_nanobsd} -c ${_target} ${_args} -j ${MAKE_JOBS}"
	echo ${_cmd}

	if sh ${TRACE} ${_cmd}
	then
		echo "${NANO_LABEL} ${_target} build PASSED"
	else
		error "${NANO_LABEL} ${_target} build FAILED; please check above log for more details"
	fi
	
	return $?
}

build_targets()
{
	#
	# For now do this iteratively. Eventually it would be nice to
	# be able to background building each target, but currently
	# that needs some more kung-fu. 
	#
	cd ${NANO_SRC}
	for _target in ${TARGETS}
	do
		build_target "${_target}"
	done
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

check_build_tools()
{
	check_for_command_from_port mkisofs sysutils/cdrtools
	check_for_command_from_port git devel/git
	check_for_command_from_port pxz archivers/pxz
	check_for_command_from_port xz archivers/xz
	check_for_command_from_port python lang/python
	check_for_command_from_port python2 lang/python2
	check_for_command_from_port VBoxManage emulators/virtualbox-ose
}

main()
{
	parse_cmdline "$@"

	#
	# Assume os-base if no targets are specified
	#
	if [ -z "${TARGETS}" ]
	then
		TARGETS="os-base"
	fi

	#
	# You must be root to build FreeNAS
	#
	set -e
	requires_root

    #
    # Do extra checks to make sure the build will succeed.
    #
    check_build_sanity

	check_build_tools

	#
	# Expand targets to their full path in the file system
	#
	expand_targets

	#
	# HACK: chmod +x the script because:
	# 1. It's not in FreeBSD proper, so it will always be touched.
	# 2. The mode is 0644 by default, and using a pattern like ${SHELL}
	#    in the Makefile snippet won't work with csh users because the
	#    script uses /bin/sh constructs.
	#
	if [ -f "${NANO_SRC}/include/mk-osreldate.sh.orig" ]
	then
		chmod +x ${NANO_SRC}/include/mk-osreldate.sh
	fi

	#
	# Now let's build the targets
	#	
	build_targets "$@"
}


main "$@"
