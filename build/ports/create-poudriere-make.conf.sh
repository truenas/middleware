#!/bin/sh
#

umask 022
cd "$(dirname "$0")/../.."
TOP="$(pwd)"
. build/nano_env

#
# Create a global make.conf file that poudriere will use
# when building packages
POUDRIERE_MAKE_CONF=${NANO_OBJ}/poudriere/etc/poudriere.d/make.conf
cat > ${POUDRIERE_MAKE_CONF} << EOF
USE_PACKAGE_DEPENDS=yes
BATCH=yes
WRKDIRPREFIX=/wrkdirs

WANT_OPENLDAP_SASL=yes

EOF

VARS="MASTER_SITE_BACKUP MASTER_SITE_OVERRIDE PACKAGEROOT PACKAGESITE MASTER_SITE_FREEBSD WITH_PKGNG DEFAULT_VERSIONS"

for var in $VARS; do
        val=$(eval echo "\$$var")
        if [ -n "$val" ]; then
                echo "$var=$val" >> "$POUDRIERE_MAKE_CONF"
        fi
done
