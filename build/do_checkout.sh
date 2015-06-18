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
. build/repos.sh

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

do_git_update()
{
    local my_branch=$1
    local my_tag=$2

    git fetch origin
    if [ "$my_tag" ] ; then
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
# Globals:
#  ${GIT_${repo_name}_REPO} - authoritive repo path
#  ${GIT_${repo_name}_BRANCH} - which branch to pull
#  ${GIT_${repo_name}_TAG} - which tag to pull, superscedes "branch"
#  ${GIT_${repo_name}_DEEP} - set to non-empty string to do a full checkout
#                            this is on by default right now.
# example:
#
#    generic_checkout_git FREEBSD "${AVATAR_ROOT}/FreeBSD/src"
#
# This will checkout into the top level the repo under $GIT_FREEBSD_REPO
# into the directory FreeBSD/src under your build directory.
#
generic_checkout_git()
{
    local repo_name=$1
    eval local checkout_path=\${GIT_${repo_name}_CHECKOUT_PATH}
    eval local my_deep=\${GIT_${repo_name}_DEEP}
    eval local my_deep=\${GIT_${repo_name}_SHALLOW}
    eval local my_repo=\${GIT_${repo_name}_REPO}
    eval local my_branch=\${GIT_${repo_name}_BRANCH}
    eval local my_tag=\${GIT_${repo_name}_TAG}

    if [ -z "$my_repo" ]; then
        echo "repo not specified!"
        exit 1
    fi

    echo "Checkout: $repo_name -> $my_repo"

    if [ "$BRANCH" ]; then
        echo "Overrding branch: ${my_branch}, using branch: ${BRANCH}"
        my_branch=${BRANCH}
    fi

    if [ "$TAG" ]; then
        echo "Overrding tag: ${my_tag}, using tag: ${TAG}"
        my_tag=${TAG}
    fi

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
    if [ -d ${checkout_path}/.git ] ; then
        ## do stuff if there is already a checkout...
        cd ${checkout_path}
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
        # do a fresh checkout...
        git clone -b "$my_branch" ${my_repo} $_depth_arg ${checkout_path}
        if [ "$my_tag" ]; then
            cd ${checkout_path}
            git checkout "$my_tag"
            cd ..
        fi
    fi
    echo $spl | grep -q x || set +x
    mkdir -p $(dirname ${SRCS_MANIFEST})
    echo "${my_repo}" `cd ${checkout_path} && git rev-parse --short HEAD` >> ${SRCS_MANIFEST}
    )
}

checkout_source()
{
    local repo

    # First try to get the freenas repo which we're building from
    if [ -f .git/config ]; then
        mkdir -p $(dirname ${SRCS_MANIFEST})
	echo $(git config --get remote.origin.url) $(git log -1 --format="%h") > ${SRCS_MANIFEST}
    fi

    for repo in ${REPOS}; do
        generic_checkout_git ${repo}
    done

    mkdir -p ${AVATAR_ROOT}/FreeBSD
    # Nuke newly created files to avoid build errors.
    git_status_ok="${AVATAR_ROOT}/FreeBSD/.git_status_ok"
    rm -rf "$git_status_ok"
    (
     cd $GIT_FREEBSD_CHECKOUT_PATH && git status --porcelain
    ) | tee "$git_status_ok"
    awk '$1 == "??" { print $2 }' < "$git_status_ok" |  xargs rm -Rf

    # Mark git clone/pull as being done already.
    echo "$NANO_LABEL" > ${AVATAR_ROOT}/FreeBSD/.pulled

    if [ ! -f "${AVATAR_ROOT}/FreeBSD/.kludged" ] && freenas_legacy_build
    then
        sed -i '' "s|mtree -deU|/usr/bin/mtree-9 -deU|g" ${NANO_SRC}/Makefile.inc1
        sed -i '' "s|mtree -deU|/usr/bin/mtree-9 -deU|g" ${NANO_SRC}/include/Makefile
        sed -i '' "s|mtree -deU|/usr/bin/mtree-9 -deU|g" ${NANO_SRC}/usr.sbin/sysinstall/install.c
        sed -i '' "s|mtree -deU|/usr/bin/mtree-9 -deU|g" ${NANO_SRC}/release/Makefile.sysinstall
	
        touch "${AVATAR_ROOT}/FreeBSD/.kludged"
    fi

    if freenas_legacy_build
    then
        if [ ! -e "/usr/bin/makeinfo" ]
        then
            cp ${NANO_KLUDGES}/makeinfo /usr/bin/makeinfo
            chmod 755 /usr/bin/makeinfo
        fi
        if [ ! -e "/usr/bin/install-info" ]
        then 
            cp ${NANO_KLUDGES}/install-info /usr/bin/install-info
            chmod 755 /usr/bin/install-info
        fi
        if [ ! -e "/usr/bin/mtree-9" ]
        then
            cp ${NANO_KLUDGES}/mtree /usr/bin/mtree-9
            chmod 755 /usr/bin/mtree-9
        fi
    fi
}

main()
{
    set -e
    checkout_source
}

main "$@"
