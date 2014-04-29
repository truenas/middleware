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
POUDRIERE_DATA=${NANO_OBJ}/ports
USE_PORTLINT=no
USE_TMPFS=yes
GIT_URL=${GIT_PORTS_REPO}
GIT_BRANCH=${GIT_PORTS_BRANCH}
EOF
    ) > ${NANO_OBJ}/poudriere/etc/poudriere.conf

    if [ -n "$PORTS_DISTFILES_CACHE" ]; then
        if [ -d "$PORTS_DISTFILES_CACHE" ]; then
            echo "DISTFILES_CACHE=\"$PORTS_DISTFILES_CACHE\"" >> ${NANO_OBJ}/poudriere/etc/poudriere.conf
        else
            echo "DISTFILES_CACHE=\"${NANO_OBJ}/ports/distfiles\"" >> ${NANO_OBJ}/poudriere/etc/poudriere.conf

            echo ""
            echo "WARNING: PORTS_DISTFILES_CACHE set in nano_env to $PORTS_DISTFILES_CACHE , but directory"
            echo "         does not exist.  Resetting PORTS_DISTFILES_CACHE to ${NANO_OBJ}/ports/distfiles"
            echo "" 
	fi
    fi
}

create_poudriere_conf
