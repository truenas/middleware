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

# Using shallow "--depth 1" git checkouts is problematic, so we default
# it to off.
#  https://github.com/phinze/homebrew-cask/issues/1003
#
# @phinze I think the only solution is for homebrew to not use --depth
# 1 in git clone. I experienced many issues with that option, and
# cloned repo practically not useable, if you want to commit something
# / browse history. Maybe it's not exactly issue with "fatal: git
# fetch-pack: expected shallow list", but generally --depth 1 causes
# lot of problems.
#
# Internally we were having trouble with not being able to incrementally
# update repos checked out with --depth1 so turn this off until we have
# a better understanding of what is going on.
if [ "x$GIT_SHALLOW" != "xyes" ] ; then
    GIT_DEEP=yes
fi

if is_truenas ; then
    # Additional repos to checkout for build
    ADDL_REPOS="$ADDL_REPOS ZFSD TRUENAS-COMPONENTS"

    : ${GIT_ZFSD_REPO=git@gitserver.ixsystems.com:/git/repos/truenas-build/git-repo/zfsd.git}
    : ${GIT_TRUENAS_COMPONENTS_REPO=git@gitserver:/git/repos/truenas-build/truenas.git}

	export NAS_PORTS_DIRECT=1

fi

if [ "${GIT_LOCATION}" = "EXTERNAL" ] ; then
    : ${GIT_FREEBSD_REPO=https://github.com/trueos/trueos}
    : ${GIT_PORTS_REPO=https://github.com/freenas/ports.git}
fi

: ${GIT_FREEBSD_BRANCH=feature/hyperv}
: ${GIT_FREEBSD_REPO=git@gitserver:/git/repos/freenas-build/trueos.git}

: ${GIT_PORTS_BRANCH=freenas/9-stable}
: ${GIT_PORTS_REPO=git@gitserver:/git/repos/freenas-build/ports.git}


# Targets to build (os-base, plugins/<plugin>).
TARGETS=""

# Should we update src + ports?
UPDATE=true
FORCE_UPDATE=false

# Trace flags
TRACE=""

# NanoBSD flags
NANO_ARGS=""

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
			FORCE_UPDATE=true # force update
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
			FORCE_UPDATE=true
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

do_git_update()
{
	local my_branch=$1
	local my_tag=$2

        git fetch origin
	if [ ! -z "$my_tag" ] ; then
		git checkout "$my_tag"
	else
	# if "my branch doesn't exist" then create it.
		if ! git rev-parse "${my_branch}" ; then
			git checkout -b ${my_branch} origin/${my_branch}
		else
			git checkout "${my_branch}"
			git pull --rebase
		fi
	fi
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
    eval local my_deep=\${GIT_${repo_name}_SHALLOW}
    eval local my_repo=\${GIT_${repo_name}_REPO}
    eval local my_branch=\${GIT_${repo_name}_BRANCH}
    eval local my_tag=\${GIT_${repo_name}_TAG}
    echo "Checkout: $repo_name -> $my_repo"
    if [ -z "$my_branch" -a -z "$my_tag" ] ; then
        my_branch=master
    fi
	(
	local spl
    spl="$-";set -x
    mkdir -p "$checkout_path"
	local _depth_arg=""
	if [ "x${GIT_SHALLOW}" = "xYES" -o "x${my_shallow}" != "xYES" ] ; then
	    _depth_arg="--depth 1"
	fi
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
        local old_branch=`git rev-parse --abbrev-ref HEAD`
		if [ "x${old_branch}" != "x${my_branch}" ]; then

            # Some forms of checkout set a specific fetch spec for only
            # the specific branch head.  Basically this means that we are
            # only going to fetch that one branch.
            #
            # Detect this scenario and remove the more specific fetch specification
            # and set our own fetch specification.
            #
            # This is somewhat ugly and I'm tempted to just set:
            #     +refs/heads/*:refs/remotes/origin/*
			if ! git config --unset remote.origin.fetch \
              "\\+refs/heads/${old_branch}:refs/remotes/origin/${old_branch}" ; then
              echo "Unable to clear old specific origin."
              echo "clearing all origins."
              git config --unset remote.origin.fetch '.*'
              git config --add remote.origin.fetch \
                "+refs/heads/*:refs/remotes/origin/*"
            else
              git config --unset remote.origin.fetch '.*'
            git config --add remote.origin.fetch \
				"+refs/heads/${my_branch}:refs/remotes/origin/${my_branch}"
            fi

            		git remote set-url origin "${my_repo}"
			git fetch origin
			do_git_update "${my_branch}" "${my_tag}"
		fi
		git pull $_depth_arg
		cd ..
	else

            git clone -b "$my_branch" ${my_repo} $_depth_arg ${checkout_name}
	fi
	echo $spl | grep -q x || set +x
	)
}

freebsd_checkout_git()
{
    generic_checkout_git FREEBSD "${AVATAR_ROOT}/FreeBSD" src
}

checkout_freebsd_source()
{
	if  ! ${UPDATE} ; then
		return
	fi

	# Don't update unless forced to or if we are building a different
	# project.
	# The file ${AVATAR_ROOT}/FreeBSD/.pulled should contain our
	# NANO_LABEL, otherwise we need to pull sources.
	if ! $FORCE_UPDATE && [ -f ${AVATAR_ROOT}/FreeBSD/.pulled ]
	then
		if [ "`cat ${AVATAR_ROOT}/FreeBSD/.pulled`" = "$NANO_LABEL" ]
		then
			echo "skipping source update because  (${AVATAR_ROOT}/FreeBSD/.pulled = NANO_LABEL($NANO_LABEL))"
			return
		else
			echo "updating because (${AVATAR_ROOT}/FreeBSD/.pulled != NANO_LABEL($NANO_LABEL))"
		fi
	fi

	if  ! ${UPDATE} ; then
		return
	fi

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
	generic_checkout_git PORTS "${AVATAR_ROOT}/FreeBSD" ports

	for proj in $ADDL_REPOS ; do
		generic_checkout_git \
			"`echo $proj|tr '-' '_'`" \
			"${AVATAR_ROOT}/nas_source" \
                   `echo $proj | tr 'A-Z' 'a-z'`
	done

	# Mark git clone/pull as being done already.
	echo "$NANO_LABEL" > ${AVATAR_ROOT}/FreeBSD/.pulled
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
    # Do extra checks to make sure the build will succeed.
    #
    check_build_sanity

	check_build_tools

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
