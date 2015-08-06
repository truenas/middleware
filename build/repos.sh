#!/bin/sh
#
# Script which defines variables which specify the repositories
# and branches to check out extra sources from.
# This script should not be called directly but should
# be included in other scripts.
#


SRCS_MANIFEST="${AVATAR_ROOT}/FreeBSD/repo-manifest"

if is_truenas ; then
    # Additional repos to checkout for build
    ADDL_REPOS="$ADDL_REPOS TRUENAS_COMPONENTS"

    : ${GIT_TRUENAS_COMPONENTS_REPO=ssh://git@github.com/iXsystems/truenas.git}
    : ${GIT_TRUENAS_COMPONENTS_CHECKOUT_PATH="${AVATAR_ROOT}/nas_source/truenas-components"}

    export NAS_PORTS_DIRECT=1
fi

: ${GIT_FREEBSD_REPO=https://github.com/trueos/trueos}
: ${GIT_PORTS_REPO=https://github.com/freenas/ports.git}
: ${GIT_LICENSELIB_REPO=https://github.com/freenas/licenselib.git}
: ${GIT_PYLIBZFS_REPO=https://github.com/freenas/py-libzfs.git}

: ${GIT_FREEBSD_BRANCH=masters/releng/9.3}
: ${GIT_FREEBSD_CHECKOUT_PATH="${AVATAR_ROOT}/FreeBSD/src"}

: ${GIT_PORTS_BRANCH=masters/2014q4}
: ${GIT_PORTS_CHECKOUT_PATH="${AVATAR_ROOT}/FreeBSD/ports"}

: ${GIT_LICENSELIB_CHECKOUT_PATH="${AVATAR_ROOT}/nas_source/licenselib"}

: ${GIT_PYLIBZFS_CHECKOUT_PATH="${AVATAR_ROOT}/nas_source/py-libzfs"}
: ${GIT_PYLIBZFS_REVCMD="rev-list HEAD --count"}
: ${REPOS="FREEBSD PORTS LICENSELIB PYLIBZFS ${ADDL_REPOS}"}
