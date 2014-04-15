#!/bin/sh
#

umask 022
cd "$(dirname "$0")/../.."
TOP="$(pwd)"
. build/nano_env
. build/repos.sh


create_poudriere_conf()
{
    # Create the main poudriere.conf file
    mkdir -p ${NANO_OBJ}/poudriere/etc
    mkdir -p ${NANO_OBJ}/poudriere/etc/poudriere.d
    (
    cat <<EOF 
NO_ZFS=yes
RESOLV_CONF=/etc/resolv.conf
BASEFS=${NANO_OBJ}/poudriere
DISTFILES_CACHE=${NANO_OBJ}/ports/distfiles
POUDRIERE_DATA=${NANO_OBJ}/d
USE_PORTLINT=no
USE_TMPFS="wrkdir data"
GIT_URL=${GIT_PORTS_REPO}
GIT_BRANCH=${GIT_PORTS_BRANCH}
EOF
    ) > ${NANO_OBJ}/poudriere/etc/poudriere.conf
}

create_poudriere_conf
