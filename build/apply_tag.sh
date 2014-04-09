#!/bin/sh
#
#

umask 022
cd "$(dirname "$0")/.."
TOP="$(pwd)"

. build/nano_env
. build/functions.sh
. build/repos.sh

apply_tag()
{
    local repo
    local repo_checkout_path

    if [ -z "$TAG" ]; then
        echo "TAG not specified"
        echo "Use:"
        echo "      make tag TAG=<tagname>"
        echo ""
        exit 1
    fi

    set -e
    # FreeNAS repo is not in REPOS variable yet
    repo_checkout_path=${AVATAR_ROOT}
    echo "Tagging $repo_checkout_path with $TAG"
    git --git-dir="$repo_checkout_path/.git" tag ${TAG_ARGS} ${TAG} 

    for repo in $REPOS ; do
        eval repo_checkout_path="\${GIT_${repo}_CHECKOUT_PATH}" 
        echo "Tagging $repo_checkout_path with $TAG"
        git --git-dir="$repo_checkout_path/.git" tag ${TAG_ARGS} ${TAG} 
    done
    set +e
}


main()
{
    apply_tag "$@"
}

main "$@"
