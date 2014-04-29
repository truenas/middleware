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

generate_poudriere_jail_conf()
{
	# Create the metadata which tells poudriere where the ports
	# building jail.  Use the world tree that was built by the FreeNAS build.
	#

	if [ ! -d ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/j ] ; then
		rm -fr ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/ja
		rm -fr ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/j
		mkdir -p ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/ja
		ln -s ja ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/j
	fi 

	JAIL=$(basename $(realpath ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/j 2> /dev/null)) 
	JAILMNT=${NANO_OBJ}/_.j
		
	echo "${NANO_OBJ}/_.j" > ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/${JAIL}/mnt
	echo "git" > ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/${JAIL}/method
	echo "${FREEBSD_RELEASE_VERSION}" > ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/${JAIL}/version
	echo "${NANO_ARCH}" > ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/${JAIL}/arch
	jail -U root -c path=${JAILMNT} command=/sbin/ldconfig -m /lib /usr/lib /usr/lib/compat
}

generate_poudriere_jail_conf
