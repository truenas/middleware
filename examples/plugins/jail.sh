#!/bin/sh

ARCH=$(uname -m)
if [ "${ARCH}" = "i386" ]
then
	TOP=/usr/pbibuild/pbiout32
	mkdir -p "${TOP}"

elif [ "${ARCH}" = "amd64" ]
then
	TOP=/usr/pbibuild/pbiout64
	mkdir -p "${TOP}"

else
	echo "${ARCH} not supported"
	exit 1
fi

MAKEOBJDIRPREFIX=${TOP}/obj
JAILSRC=${TOP}/FreeBSD/src
JAILDIR=${TOP}/plugins
SRCDIR=${JAILSRC}

export JAILDIR SRCDIR MAKEOBJDIRPREFIX ARCH


buildworld()
{
	cd ${SRCDIR}
	make TARGET_ARCH=${ARCH} DESTDIR=${JAILDIR} buildworld
}

installworld()
{
	mkdir -p ${JAILDIR}/dev
	mkdir -p ${JAILDIR}/etc
	mkdir -p ${JAILDIR}/usr/tmp
	chmod 777 ${JAILDIR}/usr/tmp

	cd ${SRCDIR}
	make TARGET_ARCH=${ARCH} DESTDIR=${JAILDIR} installworld
	cd ${SRCDIR}/etc

	make TARGET_ARCH=${ARCH} DESTDIR=${JAILDIR} distribution
	cd ${JAILDIR}

	touch ${JAILDIR}/etc/fstab
}

usage()
{
	echo "Usage: $0 <build|install> ..."
	exit 1
}

main()
{
	if [ "$#" = "0" ]
	then
		usage
	fi

	for arg in $*
	do
		case ${arg} in 
			build) buildworld;;
			install) installworld;;
		esac
	done

	exit 0
}

main $*
