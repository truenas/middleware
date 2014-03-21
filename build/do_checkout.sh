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

# only checkout sources
CHECKOUT_ONLY=false

SRCS_MANIFEST="${AVATAR_ROOT}/FreeBSD/repo-manifest"

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
    : ${GIT_TRUENAS_COMPONENTS_REPO=git@gitserver.ixsystems.com:/git/repos/truenas-build/truenas.git}

	export NAS_PORTS_DIRECT=1

fi

if [ "${GIT_LOCATION}" = "EXTERNAL" ] ; then
    : ${GIT_FREEBSD_REPO=https://github.com/trueos/trueos}
    : ${GIT_PORTS_REPO=https://github.com/freenas/ports.git}
fi

: ${GIT_FREEBSD_BRANCH=feature/unified_freebsd}
: ${GIT_FREEBSD_REPO=git@gitserver.ixsystems.com:/git/repos/freenas-build/trueos.git}

: ${GIT_PORTS_BRANCH=freenas/9-stable}
: ${GIT_PORTS_REPO=git@gitserver.ixsystems.com:/git/repos/freenas-build/ports.git}


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
	echo "${my_repo}" `cd ${checkout_name} && git rev-parse HEAD` >> ${SRCS_MANIFEST}
	)
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

	# First try to get the freenas repo which we're building from
	if [ -f .git/config ]; then
		echo `awk '/url = / {print $3}' .git/config` `git log -1 --format="%H"` > ${SRCS_MANIFEST}
	fi

	generic_checkout_git FREEBSD "${AVATAR_ROOT}/FreeBSD" src

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

check_sandbox()
{
	local status=0
	local checkout_proj_dir

	if [ ! -e ${AVATAR_ROOT}/FreeBSD/.pulled ]; then
		status=1
	fi

	if [ ! -e ${AVATAR_ROOT}/FreeBSD/src/.git ]; then
		status=1
	fi

	if [ ! -e ${AVATAR_ROOT}/FreeBSD/ports/.git ]; then
		status=1
	fi


	for proj in $ADDL_REPOS; do
		checkout_proj_dir=`echo $proj | tr 'A-Z' 'a-z'`
		if [ ! -e ${AVATAR_ROOT}/nas_source/${checkout_proj_dir} ]; then
			status=1
		fi
	done

	if [ $status -ne 0 ]; then
		echo ""
		echo "ERROR: sandbox is not fully checked out"
		echo "       Type 'env NANO_LABEL=${NANO_LABEL} make checkout' or 'env NANO_LABEL=${NANO_LABEL} make update'"
		echo "       to get all the sources from the SCM."
		echo ""
	fi

	return $status
}


main()
{
	case "$1" in
	check-sandbox)
		check_sandbox
		exit $?
		;;
	esac

	checkout_freebsd_source
}

main "$@"
