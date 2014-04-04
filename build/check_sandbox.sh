#!/bin/sh
#
#

umask 022
cd "$(dirname "$0")/.."
TOP="$(pwd)"

. build/nano_env
. build/functions.sh
. build/repos.sh

check_sandbox()
{
    local status=0
    local checkout_proj_dir

    if [ ! -e ${AVATAR_ROOT}/${EXTRA_SRC}/FreeBSD/.pulled ]; then
        status=1
    fi

    if [ ! -e ${AVATAR_ROOT}/${EXTRA_SRC}/FreeBSD/src/.git ]; then
        status=1
    fi

    if [ ! -e ${AVATAR_ROOT}/${EXTRA_SRC}/FreeBSD/ports/.git ]; then
        status=1
    fi


    for proj in $ADDL_REPOS; do
        checkout_proj_dir=`echo $proj | tr 'A-Z' 'a-z'`
        if [ ! -e ${AVATAR_ROOT}/${EXTRA_SRC}/nas_source/${checkout_proj_dir}/.git ]; then
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
    check_sandbox
}

main "$@"
