#!/bin/sh
#

umask 022
cd "$(dirname "$0")/../.."
TOP="$(pwd)"
. build/nano_env
. build/functions.sh
. build/repos.sh

cleanup()
{
	echo "Cleaning up jail...."
	sleep 3
	umountfs ${NANO_OBJ}/_.j

	for d in $EXTRA_PORT_DIRS; do
		[ -d  "${GIT_PORTS_CHECKOUT_PATH}/${d}" ] && rm -fr "${GIT_PORTS_CHECKOUT_PATH}/${d}"
	done
}

# XX: Uncomment to debug
#TRACE=-x

trap cleanup EXIT

EXTRA_PORT_DIRS="sysutils/zfsd misc/truenas-files misc/freenas-files"

for d in $EXTRA_PORT_DIRS; do
	mkdir -p "${GIT_PORTS_CHECKOUT_PATH}/${d}"
done

mount -t nullfs -o ro ${GIT_FREEBSD_CHECKOUT_PATH} ${NANO_OBJ}/_.j/usr/src  || exit 1
#mount -t nullfs -o ro ${AVATAR_ROOT}/src ${NANO_OBJ}/_.j/usr/nas_source2 || exit 1
cp -a ${AVATAR_ROOT}/src/ ${NANO_OBJ}/_.j/usr/nas_source2 
cp -a ${AVATAR_ROOT}/nas_ports/sysutils/zfsd ${GIT_PORTS_CHECKOUT_PATH}/sysutils 
cp -a ${AVATAR_ROOT}/nas_ports/misc/truenas-files ${GIT_PORTS_CHECKOUT_PATH}/misc 
cp -a ${AVATAR_ROOT}/nas_ports/misc/freenas-files ${GIT_PORTS_CHECKOUT_PATH}/misc

MAKE_JOBS=$(sysctl -n kern.smp.cpus)
if [ ${MAKE_JOBS} -gt 10 ]; then
        MAKE_JOBS=$((${MAKE_JOBS} - 3 ))
fi

mkdir -p ${NANO_OBJ}/ports/distfiles
poudriere ${TRACE} -e ${NANO_OBJ}/poudriere/etc bulk -w -J ${MAKE_JOBS} -f ${NANO_OBJ}/poudriere/etc/ports.txt -j j -p p
