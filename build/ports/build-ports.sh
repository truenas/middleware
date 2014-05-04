#!/bin/sh
#

umask 022
cd "$(dirname "$0")/../.."
TOP="$(pwd)"
. build/nano_env
. build/functions.sh
. build/poudriere-functions.sh
. build/repos.sh
. build/ports/ports_funcs.sh

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
JAIL=$(basename $(realpath ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/j 2> /dev/null))
: ${PORTSLIST:=${NANO_OBJ}/poudriere/etc/ports.txt}
: ${PORTS:=p}

if [ -z "$JAIL" ]; then
	echo "ERROR: jail does not exist"
	exit 1
fi

if [ -n "$JAIL" ]; then
	jls -n -q -j "${JAIL}-${PORTS}" 2> /dev/null
	if [ $? -eq 0 ]; then
		# Jail named ${JAIL}-${PORTS} is running, we need to choose another jail name
		OLD_JAILNAME="$JAIL"
		JAIL=$(get_unique_jailname)
		if [ -z "$JAIL" ]; then
			echo "ERROR: No available jail name"
			exit 1
		fi
		rm -fr ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/${JAIL}
		mv ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/${OLD_JAILNAME} ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/${JAIL}
		rm -fr ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/j
		ln -s ${JAIL} ${NANO_OBJ}/poudriere/etc/poudriere.d/jails/j
		for d in build cache packages; do
			rm -fr ${NANO_OBJ}/ports/${d}/${JAIL}-${PORTS}
			[ -d ${NANO_OBJ}/ports/${d}/${OLD_JAILNAME}-${PORTS} ] && mv ${NANO_OBJ}/ports/${d}/${OLD_JAILNAME}-${PORTS} ${NANO_OBJ}/ports/${d}/${JAIL}-${PORTS}
		done
	fi
fi


poudriere ${TRACE} -e ${NANO_OBJ}/poudriere/etc bulk -w -J ${MAKE_JOBS} -f ${PORTSLIST} -j "$JAIL" -p ${PORTS}
