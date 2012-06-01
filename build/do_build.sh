#!/bin/sh
#
# See README for up to date usage examples.
#

cd "$(dirname "$0")/.."

. build/nano_env
. build/functions.sh
. build/pbi_env

# Should we build?
BUILD=true

# 0 - build only what's required (src, ports, diskimage, etc).
# 1 - force src build.
# 2 - nuke the obj directories (os-base.*, etc) and build from scratch.
#FORCE_BUILD=0

# Number of jobs to pass to make. Only applies to src so far.
MAKE_JOBS=$(( 2 * $(sysctl -n kern.smp.cpus) + 1 ))
export MAKE_JOBS

# Available targets to build
BUILD_TARGETS="\
os-base \
plugins-base \
plugins/transmission \
plugins/firefly \
plugins/minidlna \
"

# Targets to build (os-base, plugins-base, plugins/<plugin>).
TARGETS=""

# Should we update src + ports?
UPDATE=true
if [ -f ${AVATAR_ROOT}/FreeBSD/.pulled ]
then
	UPDATE=false
fi

# Trace flags
TRACE=""

# NanoBSD flags
NANO_ARGS=""


usage() {
	cat <<EOF
usage: ${0##*/} [-aBfsux] [-j make-jobs] [-t target1] [-t target2] [ -t ...] [-- nanobsd-options]

-a		- Build all targets
-B		- don't build. Will pull the sources and show you the
		  nanobsd.sh invocation string instead. 
-f  		- if not specified, will pass either -b (if prebuilt) to
		  nanobsd.sh, or nothing if not prebuilt. If specified once,
		  force a buildworld / buildkernel (passes -n to nanobsd). If
		  specified twice, this won't pass any options to nanobsd.sh,
		  which will force a pristine build.
-j make-jobs	- number of make jobs to run; defaults to ${MAKE_JOBS}.
-s		- show build targets
-t target	- target to build (os-base, plugins-base, <plugin-name>, etc).
		  This switch can be used more than once to specify multiple targets.
-u		- force an update via csup (warning: there are potential
		  issues with newly created files via patch -- use with
		  caution).
-x		- enable sh -x debugging
EOF
	exit 1
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
	while getopts 'aBfj:st:ux' _optch
	do
		case "${_optch}" in
		a)
			TARGETS="${BUILD_TARGETS}"
			;;
		B)
			BUILD=false
			;;
		f)
			: $(( FORCE_BUILD += 1 ))
			;;
		j)
			echo ${OPTARG} | egrep -q '^[[:digit:]]+$' && [ ${OPTARG} -le 0 ]
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
		u)
			UPDATE=true
			;;
		x)
			TRACE="-x"
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

is_plugin()
{
	local _res=1
	local _target="${1}"

	if echo "${_target}" | grep -E "^${NANO_CFG_BASE}\/plugins\/" >/dev/null 2>&1	
	then
		_res=0
	fi

	return ${_res}
}

build_target()
{
	local _target="${1}"
	local _args="${NANO_ARGS}"
	local _nanobsd="${AVATAR_ROOT}/build/nanobsd/nanobsd.sh"

	export AVATAR_COMPONENT=${_target##*/}

	#
	# XXX: chicken and egg problem. Not doing this will always cause plugins-base,
	# etc to rebuild if os-base isn't already present, or the build to fail if
	# os-base is built and plugins-base isn't, etc.
	#
	export NANO_OBJ=${AVATAR_ROOT}/${AVATAR_COMPONENT}/${NANO_ARCH}

	#
	# FORCE_BUILD is unset -- apply sane defaults based on what's already been built.
	#
	if [ -z "${FORCE_BUILD}" ]
	then
		FORCE_BUILD=0

		local _required_logs="_.iw"
		if [ "${AVATAR_COMPONENT}" = "os-base" ]
		then
			#
			# The base OS distro requires a kernel build.
			#
			_required_logs="_.ik _.iw"

		#
		# For plugins, we don't need to build a NanoBSD image, however, the PBI
		# tools will build a chroot and use it in the future for all plugin builds.
		#
		elif is_plugin "${_target}"
		then
			_required_logs=""
		fi

		for _required_log in ${_required_logs}
		do
			if [ ! -s "${NANO_OBJ}/${_required_log}" ]
			then
				FORCE_BUILD=2
				break
			fi
		done
	fi

	if [ "${FORCE_BUILD}" = "0" ]
	then
		_args="${_args} -b"

	elif [ "${FORCE_BUILD}" = "1" ]
	then
		_args="${_args} -n"
	fi
	export FORCE_BUILD

	local _cmd="${_nanobsd} -c ${_target} ${_args} -j ${MAKE_JOBS}"

	if ! $BUILD
	then
		exit 0
	fi

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

		#
		# Start off with a clean slate for each target
		#
		unset FORCE_BUILD

		build_target "${_target}"
	done
}

checkout_freebsd_source()
{
	if ${UPDATE}
	then
		if [ -z "${FREEBSD_CVSUP_HOST}" ]
		then
			error "No sup host defined, please define FREEBSD_CVSUP_HOST and rerun"
		fi
		mkdir -p ${AVATAR_ROOT}/FreeBSD

		: ${FREEBSD_SRC_REPOSITORY_ROOT=http://svn.freebsd.org/base}
		FREEBSD_SRC_URL_REL="releng/8.2"
		FREEBSD_SRC_URL_FULL="${FREEBSD_SRC_REPOSITORY_ROOT}/${FREEBSD_SRC_URL_REL}"

		(
	 		cd "${AVATAR_ROOT}/FreeBSD"
	 		if [ -d src/.svn ]; then
				svn switch ${FREEBSD_SRC_URL_FULL} src
				svn upgrade src >/dev/null 2>&1 || :
	 			svn resolved src
	 		else
				svn co ${FREEBSD_SRC_URL_FULL} src
	 		fi

			#
	 		# Always do this so the csup pulled files are paved over.
			#
 	 		svn revert -R src
	 		svn up src
		)

		SUPFILE=${AVATAR_ROOT}/FreeBSD/supfile
		cat <<EOF > ${SUPFILE}
*default host=${FREEBSD_CVSUP_HOST}
*default base=${AVATAR_ROOT}/FreeBSD/sup
*default prefix=${AVATAR_ROOT}/FreeBSD
*default release=cvs
*default delete use-rel-suffix
*default compress

ports-all date=2011.12.28.00.00.00
EOF
		#
		# Nuke newly created files to avoid build errors.
		#
		svn_status_ok="${AVATAR_ROOT}/FreeBSD/.svn_status_ok"
		rm -f "${svn_status_ok}"
		(
	 		svn status ${AVATAR_ROOT}/FreeBSD/src
	 		: > "${svn_status_ok}"
		) | \
			awk '$1 == "?" { print $2 }' | \
			xargs rm -Rf
		[ -f "${svn_status_ok}" ]

		for file in $(find ${AVATAR_ROOT}/FreeBSD/ports -name '*.orig' -size 0)
		do
			rm -f "$(echo ${file} | sed -e 's/.orig$//')"
		done

		echo "Checking out ports tree from ${FREEBSD_CVSUP_HOST}..."
		csup -L 1 ${SUPFILE}

		#
		# Force a repatch.
		#
		: > ${AVATAR_ROOT}/FreeBSD/src-patches
		: > ${AVATAR_ROOT}/FreeBSD/ports-patches
		: > ${AVATAR_ROOT}/FreeBSD/.pulled
	fi
}

apply_patches()
{
	local _lp=last-patch.$$.log

	#
	# Appply patches to FreeBSD source code
	#
	for _patch in $(cd ${AVATAR_ROOT}/patches && ls freebsd-*.patch)
	do
		if ! grep -q ${_patch} ${AVATAR_ROOT}/FreeBSD/src-patches
		then
			echo "Applying patch ${_patch}..."
			(
				cd FreeBSD/src &&
		 		patch -C -f -p0 < ${AVATAR_ROOT}/patches/${_patch} >${_lp} 2>&1 ||
		 		{ echo "Failed to apply patch: ${_patch} (check $(pwd)/${_lp})"; exit 1; } &&
		 		patch -E -p0 -s < ${AVATAR_ROOT}/patches/${_patch}
			)
			echo ${_patch} >> ${AVATAR_ROOT}/FreeBSD/src-patches
		fi
	done

	#
	# Apply patches to FreeBSD ports
	#
	for _patch in $(cd ${AVATAR_ROOT}/patches && ls ports-*.patch)
	do
		if ! grep -q ${_patch} ${AVATAR_ROOT}/FreeBSD/ports-patches
		then
			echo "Applying patch ${_patch}..."
			(
				cd FreeBSD/ports &&
		 		patch -C -f -p0 < ${AVATAR_ROOT}/patches/${_patch} >${_lp} 2>&1 ||
				{ echo "Failed to apply patch: ${_patch} (check $(pwd)/${_lp})"; exit 1; } &&
		 		patch -E -p0 -s < ${AVATAR_ROOT}/patches/${_patch}
			)
			echo ${_patch} >> ${AVATAR_ROOT}/FreeBSD/ports-patches
		fi
	done
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
	if $BUILD
	then
		requires_root
	fi

	#
	# Expand targets to their full path in the file system
	#
	expand_targets

	#
	# If UPDATE is set, we need to grab the FreeBSD source code
	#
	checkout_freebsd_source

	#
	# Apply source and port patches to FreeBSD source code
	#
	apply_patches

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
