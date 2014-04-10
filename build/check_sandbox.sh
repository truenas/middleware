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
    local repo_name

    if [ ! -e ${AVATAR_ROOT}/${EXTRA_SRC}/FreeBSD/.pulled ]; then
        status=1
    fi

    for repo_name in $REPOS; do
        eval local checkout_path=\${GIT_${repo_name}_CHECKOUT_PATH}
        if [ ! -e "${checkout_path}/.git" ]; then
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
