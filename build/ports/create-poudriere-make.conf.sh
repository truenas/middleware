#!/bin/sh
#

umask 022
cd "$(dirname "$0")/../.."
TOP="$(pwd)"
. build/nano_env

#
# Create a global make.conf file that poudriere will use
# when building packages
cat > ${NANO_OBJ}/poudriere/etc/poudriere.d/make.conf << EOF
USE_PACKAGE_DEPENDS=yes
BATCH=yes
WRKDIRPREFIX=/wrkdirs

WANT_OPENLDAP_SASL=yes

EOF
