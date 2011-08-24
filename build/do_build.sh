#!/bin/sh

# interface:
# cd to top of tree
# sh ./build/do_build.sh
# magic happens :)
#

if [ $(id -ru) -ne 0 ]; then
	echo "You must be root to run this"
	exit 1
fi

root=$(pwd)
: ${FREENAS_ARCH=$(uname -p)}
export FREENAS_ARCH
export NANO_OBJ=${root}/obj.${FREENAS_ARCH}
PREP_SOURCE=${PREP_SOURCE:-""}

# Make sure we have FreeBSD dirs
if [ ! -d FreeBSD ]; then
	mkdir -p FreeBSD/src
	mkdir -p FreeBSD/ports
fi

# Make sure we have FreeBSD src, fetch using csup if not
if [ ! -f FreeBSD/supfile -o -n "$force_update" ]; then
	if [ -z "$FREEBSD_CVSUP_HOST" ]; then
		echo "No sup host defined, please define FREEBSD_CVSUP_HOST and rerun"
		exit 1
	fi
	echo "Checking out tree from ${FREEBSD_CVSUP_HOST}..."
	cat <<EOF > FreeBSD/supfile
*default host=${FREEBSD_CVSUP_HOST}
*default base=${root}/FreeBSD/sup
*default prefix=${root}/FreeBSD
*default release=cvs
*default delete use-rel-suffix

src-all tag=RELENG_8_2
ports-all date=2011.07.17.00.00.00
EOF
	csup -L 1 ${root}/FreeBSD/supfile
	# Force a repatch because csup pulls pristine sources.
	rm -f ${root}/FreeBSD/src-patches
	rm -f ${root}/FreeBSD/ports-patches
fi

# Make sure that all the patches are applied
touch ${root}/FreeBSD/src-patches
for i in $(cd ${root}/patches && echo freebsd-*.patch); do
	if ! grep -q $i ${root}/FreeBSD/src-patches; then
		echo "Applying patch $i..."
		(cd FreeBSD/src && patch -p0 < ${root}/patches/$i)
		echo $i >> ${root}/FreeBSD/src-patches
	fi
done
touch ${root}/FreeBSD/ports-patches
for i in $(cd ${root}/patches && echo ports-*.patch); do
	if ! grep -q $i ${root}/FreeBSD/ports-patches; then
		echo "Applying patch $i..."
		(cd FreeBSD/ports && patch -p0 < ${root}/patches/$i)
		echo $i >> ${root}/FreeBSD/ports-patches
	fi
done

if [ -n "${PREP_SOURCE}" ]; then
	exit
fi

# OK, now we can build
cd FreeBSD/src
args="-c ../../nanobsd/freenas-common"
if [ -d ${NANO_OBJ} ]; then
	extra_args="-b"
fi
for i in $*; do
	case $i in
	-f)
		extra_args="" ;;
	*)	args="$args $i" ;;
	esac
done
echo tools/tools/nanobsd/nanobsd.sh $args $extra_args
sh tools/tools/nanobsd/nanobsd.sh $args $extra_args
if [ $? -eq 0 ]; then
	REVISION=$(svnversion ${root})
	NANO_NAME="FreeNAS-8r${REVISION}-${FREENAS_ARCH}"
	xz -f ${NANO_OBJ}/_.disk.image
	mv ${NANO_OBJ}/_.disk.image.xz ${NANO_OBJ}/${NANO_NAME}.xz
	sha256 ${NANO_OBJ}/${NANO_NAME}.xz
fi
