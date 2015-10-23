#!/bin/sh
#
#

umask 022
cd "$(dirname "$0")/.."
TOP="$(pwd)"

. build/nano_env
. build/functions.sh
. build/repos.sh

create_plugin()
{
    VCENTER_PLUGIN_DIR="${AVATAR_ROOT}/nas_source/truenas-vcenter-components/vcp"
    eval "cd ${VCENTER_PLUGIN_DIR}; mvn clean install;cd -"
    VCENTER_PLUGIN=${VCENTER_PLUGIN_DIR}/vcp-bundle/target/plugin_*
    eval "cp ${VCENTER_PLUGIN} ${AVATAR_ROOT}"
    eval "rm -rf ${AVATAR_ROOT}/nas_source/truenas-vcenter-components/"
}


main()
{
    create_plugin
}

main "$@"
