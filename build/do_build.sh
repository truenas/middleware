#!/bin/sh
#
# See README for up to date usage examples.
#

umask 022
cd "$(dirname "$0")/.."
TOP="$(pwd)"

. build/nano_env
. build/functions.sh

# Should we build?
BUILD=true

# only checkout sources
CHECKOUT_ONLY=false

# 0 - build only what's required (src, ports, diskimage, etc).
# 1 - force src build.
# 2 - nuke the obj directories (os-base.*, etc) and build from scratch.
#FORCE_BUILD=0

# Number of jobs to pass to make. Only applies to src so far.
MAKE_JOBS=$(( 2 * $(sysctl -n kern.smp.cpus) + 1 ))
if [ ${MAKE_JOBS} -gt 10 ]; then
	MAKE_JOBS=10
fi
export MAKE_JOBS

# Available targets to build
BUILD_TARGETS="os-base"

ADDL_REPOS=""

if is_truenas ; then
    GIT_DEEP=yes  # shallow checkouts cause too many problems right now.
    # Additional repos to checkout for build
    ADDL_REPOS="$ADDL_REPOS ZFSD TRUENAS-FILES"

    : ${GIT_ZFSD_REPO=git@gitserver.ixsystems.com:/git/repos/truenas-build/git-repo/zfsd.git}
    : ${GIT_TRUENAS_FILES_REPO=git@gitserver.ixsystems.com:/git/repos/truenas-build/git-repo/truenas-files.git}
fi

# Targets to build (os-base, plugins/<plugin>).
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

: ${GIT_FREEBSD_CACHE="file:///freenas-build/trueos.git"}
if [ -e "${GIT_FREEBSD_CACHE##file://}" ]; then
        echo "Using local mirror in $GIT_FREEBSD_CACHE"
else
        echo "no local mirror, to speed up builds we suggest doing"
        echo "'git clone --mirror ${GIT_FREEBSD_REPO} into ${GIT_FREEBSD_CACHE}"
fi

: ${GIT_PORTS_CACHE="file:///freenas-build/ports.git"}
if [ -e "${GIT_PORTS_CACHE##file://}" ]; then
    echo "Using local git ports mirror in $GIT_PORTS_REPO"
else
    echo "no local mirror, to speed up builds we suggest doing"
    echo "'git clone --mirror https://github.com/freenas/ports.git into ${HOME}/freenas/git/ports.git"
fi

usage() {
	cat <<EOF
usage: ${0##*/} [-aBfJsux] [-j make-jobs] [-t target1] [-t target2] [ -t ...] [-- nanobsd-options]

-a		- Build all targets
-B		- don't build. Will pull the sources and show you the
		  nanobsd.sh invocation string instead. 
-c		- Only checkout the source code don't do anything else.
-f  		- if not specified, will pass either -b (if prebuilt) to
		  nanobsd.sh, or nothing if not prebuilt. If specified once,
		  force a buildworld / buildkernel (passes -n to nanobsd). If
		  specified twice, this won't pass any options to nanobsd.sh,
		  which will force a pristine build.
-j make-jobs	- number of make jobs to run; defaults to ${MAKE_JOBS}.
-J		- Build with jails
-s		- show build targets
-t target	- target to build (os-base, <plugin-name>, etc).
		  This switch can be used more than once to specify multiple targets.
-u		- force an update via csup (warning: there are potential
		  issues with newly created files via patch -- use with
		  caution).
-x		- enable sh -x debugging
-z		- End script before images are built.  This is useful for
		  preloading a package build so you can do a full build after this
		  and compress the resulting thin image.

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
	while getopts 'aBcfj:st:uxz' _optch
	do
		case "${_optch}" in
		a)
			TARGETS="${BUILD_TARGETS}"
			;;
		B)
			BUILD=false
			;;
        c)  CHECKOUT_ONLY=true
            UPDATE=true # force update
            ;;
		f)
			: $(( FORCE_BUILD += 1 ))
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
		u)
			UPDATE=true
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
	local _fb=${FORCE_BUILD}
	local _c

	export AVATAR_COMPONENT=${_target##*/}

	#
	# XXX: chicken and egg problem. Not doing this will always cause plugins-base,
	# etc to rebuild if os-base isn't already present, or the build to fail if
	# os-base is built and plugins-base isn't, etc.
	#
	export NANO_OBJ=${AVATAR_ROOT}/${AVATAR_COMPONENT}/${NANO_ARCH}

	#
	# _fb is unset -- apply sane defaults based on what's already been built.
	#
	if [ -z "${_fb}" ]
	then
		_fb=0

		local _required_logs="_.iw"
		if [ "${AVATAR_COMPONENT}" = "os-base" ]
		then
			#
			# The base OS distro requires a kernel build.
			#
			_required_logs="_.ik _.iw"
		fi

		for _required_log in ${_required_logs}
		do
			if [ ! -s "${NANO_OBJ}/${_required_log}" ]
			then
				_fb=2
				break
			fi
		done
	fi

	if [ "${_fb}" = "0" ]
	then
		_args="${_args} -b"

	elif [ "${_fb}" = "1" ]
	then
		_args="${_args} -n"
		_c=$(echo ${AVATAR_COMPONENT} | tr '-' '_')
		
		export "${_c}_FORCE=1"
	fi

	local _cmd="${_nanobsd} -c ${_target} ${_args} -j ${MAKE_JOBS}"

	if ! $BUILD
	then
		echo ${_cmd}
		exit 0
	fi

	if [ -n "${TRACE}" ] ; then
		echo ${_cmd}
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
		build_target "${_target}"
	done
}

#
# Checkout a module, expects the following parameters:
#  $1 - repo_name, (example: FREEBSD, PORTS, ZFSD) this variable will be
#       expanded for globals below.  "${GIT_${repo_name}_REPO}" to get the
#       rest of the information for branch, repo, cache, etc.
#  $2 - checkout_path where to checkout the code under the build dir.
#       You probably want to prefix with ${AVATAR_ROOT}
#       (example "${AVATAR_ROOT}/FreeBSD")
#  $3 - Actual name the git checkout should be done under.
# Globals:
#  ${GIT_${repo_name}_REPO} - authoritive repo path
#  ${GIT_${repo_name}_CACHE} - (optional) mirror location that is faster
#                              to clone from
#  ${GIT_${repo_name}_BRANCH} - which branch to pull
#  ${GIT_${repo_name}_TAG} - which tag to pull, superscedes "branch"
#  ${GIT_${repo_name}_DEEP} - set to non-empty string to do a full checkout
#                            this is on by default right now.
# example:
#
#    generic_checkout_git FREEBSD "${AVATAR_ROOT}/FreeBSD" src
# This will checkout into the top level the repo under $GIT_FREEBSD_REPO
# into the directory FreeBSD/src under your build directory.
#
generic_checkout_git()
{
    local repo_name=$1
    local checkout_path=$2
    local checkout_name=$3
    eval local my_deep=\${GIT_${repo_name}_DEEP}
    eval local my_repo=\${GIT_${repo_name}_REPO}
    eval local my_cache=\${GIT_${repo_name}_CACHE}
    eval local my_branch=\${GIT_${repo_name}_BRANCH}
    eval local my_tag=\${GIT_${repo_name}_TAG}
    echo "Checkout: $repo_name -> $my_repo"
	(
	local spl
    spl="$-";set -x
    mkdir -p "$checkout_path"
	local _depth_arg="--depth 1"
	# If tags are set, then it appears we need a full checkout to get
	# the tags.  If GIT_DEEP is set, then we don't want a shallow
	# copy because we need to tag for a release or otherwise work
	# on the repo we are cloning.
	if [ "x${GIT_DEEP}" != "x" -o "x${my_deep}" != "x" ] ; then
		_depth_arg=""
	fi
	cd "${checkout_path}"

	# XXX: there are a few git fetch commands below.
	#  can we optimize by using
	#  git remote add -t remote-branch remote-name remote-url  ?
	#  instead of a fetch of all of origin?
	if [ -d ${checkout_name}/.git ] ; then
		cd ${checkout_name}
		if [ "x`git rev-parse --abbrev-ref HEAD`" != "x${my_branch}" ]; then
			git fetch origin

			git checkout ${my_branch}
		fi
		git pull $_depth_arg
		cd ..
	else
        local branch

        if [ "x${my_tag}" != "x" ] ; then
            branch="${my_tag}"
        else
            branch=${my_branch}
        fi
        if [ -z "$branch" ] ; then
            branch=master
        fi
        if [ -e "${my_cache##file://}" ]; then
            git clone ${my_cache} ${checkout_name}
            cd ${checkout_name}
            git remote set-url origin "${my_repo}"
            git fetch origin
            git checkout "$branch"
        else
		    git clone -b "$branch" ${my_repo} $_depth_arg ${checkout_name}
        fi
	fi
	echo $spl | grep -q x || set +x
	)
}

freebsd_checkout_git()
{
	: ${GIT_FREEBSD_BRANCH=feature/unified_freebsd}
	: ${GIT_FREEBSD_REPO=git@gitserver:/git/repos/freenas-build/trueos.git}
    generic_checkout_git FREEBSD "${AVATAR_ROOT}/FreeBSD" src
}

checkout_freebsd_source()
{
	if ${UPDATE}
	then
		mkdir -p ${AVATAR_ROOT}/FreeBSD

			echo "Use git set!"
			freebsd_checkout_git

			# Nuke newly created files to avoid build errors.
			git_status_ok="$AVATAR_ROOT/FreeBSD/.git_status_ok"
			rm -rf "$git_status_ok"
			(
			  cd $AVATAR_ROOT/FreeBSD/src && git status --porcelain
			) | tee "$git_status_ok"
			awk '$1 == "??" { print $2 }' < "$git_status_ok" |  xargs rm -Rf

			# Checkout git ports
		    : ${GIT_PORTS_BRANCH=freenas/9.1-stable-a}
		    : ${GIT_PORTS_REPO=git@gitserver:/git/repos/freenas-build/ports.git}
            generic_checkout_git PORTS "${AVATAR_ROOT}/FreeBSD" ports

            for proj in $ADDL_REPOS ; do
                generic_checkout_git \
                    "`echo $proj|tr '-' '_'`" \
                    "${AVATAR_ROOT}/nas_source" \
                    `echo $proj | tr 'A-Z' 'a-z'`
            done

		#
		# Force a repatch.
		#
		: > ${AVATAR_ROOT}/FreeBSD/.pulled
	fi
}

do_pbi_wrapper_hack()
{
	local _src="${AVATAR_ROOT}/src/pcbsd/pbi-wrapper"
	local _dst="${AVATAR_ROOT}/FreeBSD/src/pbi-wrapper"

	if [ ! -d "${_dst}" ]
	then
		mkdir -p "${_dst}"
	fi
	cp ${_src}/* ${_dst}

	NANO_LOCAL_DIRS="${NANO_LOCAL_DIRS} pbi-wrapper"
	export NANO_LOCAL_DIRS
}

do_extract_tarball_hack()
{
	local _src="${AVATAR_ROOT}/src/extract-tarball"
	local _dst="${AVATAR_ROOT}/FreeBSD/src/extract-tarball"

	if [ ! -d "${_dst}" ]
	then
		mkdir -p "${_dst}"
	fi
	cp ${_src}/* ${_dst}

	NANO_LOCAL_DIRS="${NANO_LOCAL_DIRS} extract-tarball"
	export NANO_LOCAL_DIRS
}

main()
{
	parse_cmdline "$@"

    if $CHECKOUT_ONLY ; then
        set -e
        checkout_freebsd_source
        exit 0
    fi

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
	# pbiwrapper hacks
	#
	do_pbi_wrapper_hack

	#
	# compile extract-tarball during FreeBSD world build
	#
	do_extract_tarball_hack

	#
	# Now let's build the targets
	#	
	build_targets "$@"
}


main "$@"
