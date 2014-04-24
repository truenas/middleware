#!/bin/sh
#

umask 022
cd "$(dirname "$0")/../.."
TOP="$(pwd)"
. build/nano_env

# XX: Uncomment the following to test using poudriere to create the
#     ports building jail.  poudriere builds the jail based on distribution files of
#     FreeBSD releases.
#poudriere -e ${NANO_OBJ}/poudriere/etc jail -c -j freebsd:9:x86:64 -v 9.2-RELEASE-p3 -a amd64

# Create the metadata which tells poudriere where the ports
# building jail.  Use the world tree that was built by the FreeNAS build.
#
JAIL=j
JAILMNT=${NANO_OBJ}/_.j
mkdir -p ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/${JAIL}
echo "${NANO_OBJ}/_.j" > ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/${JAIL}/mnt
echo "git" > ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/${JAIL}/method
echo "${FREEBSD_RELEASE_VERSION}" > ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/${JAIL}/version
echo "${NANO_ARCH}" > ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/${JAIL}/arch

jail -U root -c path=${JAILMNT} command=/sbin/ldconfig -m /lib /usr/lib /usr/lib/compat
