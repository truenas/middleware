#!/bin/sh
#
# Build (either from scratch or using cached files):
# 	sh build/do_build.sh
#
# Force a resync/repatch of just ports:
#	sh build/do_build.sh -f ports
#
# Force a resync/repatch of everything:
#	sh build/do_build.sh -f all
#
# Just pull the sources:
#	sh build/do_build.sh -B
#

error() {
	echo >&2 "${0##/*}: ERROR: $*"
	exit 1
}

usage() {
	echo "usage: ${0##*/} [-B] [-f ports|all] [-- nanobsd-options]"
	exit 1
}

cd "$(dirname "$0")/.."

BUILD=true
FORCE_UPDATE=false
FORCE_REBUILD_PORTS=false
FORCE_REBUILD_SRC=false

while getopts 'f:' optch; do
	case "$optch" in
	B)
		echo "will not build"
		BUILD=false
		;;
	f)
		FORCE_UPDATE=true
		case "$OPTARG" in
		all)
			FORCE_REBUILD_PORTS=true
			FORCE_REBUILD_SRC=true
			;;
		ports)
			FORCE_REBUILD_PORTS=true
			;;
		src)
			FORCE_REBUILD_SRC=true
			;;
		*)
			usage
			;;
		esac
		;;
	\?)
		usage
		;;
	esac
done
shift $(( $OPTIND - 1 ))

if [ $(id -ru) -ne 0 ]; then
	error "You must be root when running $0"
fi

root=$(pwd)
: ${FREENAS_ARCH=$(uname -p)}
export FREENAS_ARCH
export NANO_OBJ=${root}/obj.${FREENAS_ARCH}

if [ ! -d FreeBSD ]; then
	mkdir FreeBSD
fi

# Make sure we have FreeBSD src, fetch using csup if not
if [ ! -f FreeBSD/supfile ] || "$FORCE_UPDATE"; then
	if [ -z "$FREEBSD_CVSUP_HOST" ]; then
		error "No sup host defined, please define FREEBSD_CVSUP_HOST and rerun"
	fi
	echo "Checking out tree from ${FREEBSD_CVSUP_HOST}..."
	cat <<EOF > FreeBSD/supfile
*default host=${FREEBSD_CVSUP_HOST}
*default base=${root}/FreeBSD/sup
*default prefix=${root}/FreeBSD
*default release=cvs
*default delete use-rel-suffix
*default compress

src-all tag=RELENG_8_2
ports-all date=2011.07.17.00.00.00
EOF
	csup -L 1 FreeBSD/supfile
	# Force a repatch because csup pulls pristine sources.
	: > ${root}/FreeBSD/src-patches
	: > ${root}/FreeBSD/ports-patches

	# XXX: work around a bug in csup where it doesn't clean out all
	# mime-types, as it nukes certain types (.c, .h, etc) files properly.
	#
	# Nuke the newly created files to avoid build errors, as patch(1)
	# will automatically append to the previously non-existent file.
	for file in $(find FreeBSD/ -name '*.orig' -size 0); do
		rm -f "$(echo "$file" | sed -e 's/.orig//')"
	done
fi

# Make sure that all the patches are applied
for i in $(cd ${root}/patches && echo freebsd-*.patch); do
	if ! grep -q $i ${root}/FreeBSD/src-patches; then
		echo "Applying patch $i..."
		(cd FreeBSD/src && patch -p0 < ${root}/patches/$i)
		echo $i >> ${root}/FreeBSD/src-patches
	fi
done
for i in $(cd ${root}/patches && echo ports-*.patch); do
	if ! grep -q $i ${root}/FreeBSD/ports-patches; then
		echo "Applying patch $i..."
		(cd FreeBSD/ports && patch -p0 < ${root}/patches/$i)
		echo $i >> ${root}/FreeBSD/ports-patches
	fi
done

if ! $BUILD; then
	exit 0
fi

# OK, now we can build
cd FreeBSD/src
args="-c ${root}/nanobsd/freenas-common"
# Make installworld a worthy sentinel for determining whether or not to
# rebuild things by default... nuke this file if you disagree or use -f src.
if [ -s ${NANO_OBJ}/_.iw ] && ! "$FORCE_REBUILD_SRC"; then
	extra_args="-b"
fi
rm -f ${NANO_OBJ}/_.iw
if $FORCE_REBUILD_PORTS; then
	find $NANO_OBJ/ports/packages/ 2>/dev/null | xargs -n 1 rm -Rf
fi
echo tools/tools/nanobsd/nanobsd.sh $args $* $extra_args
if sh tools/tools/nanobsd/nanobsd.sh $args $* $extra_args; then
	REVISION=$(svnversion ${root})
	NANO_NAME="FreeNAS-8r${REVISION}-${FREENAS_ARCH}"
	xz -f ${NANO_OBJ}/_.disk.image
	mv ${NANO_OBJ}/_.disk.image.xz ${NANO_OBJ}/${NANO_NAME}.xz
	sha256 ${NANO_OBJ}/${NANO_NAME}.xz
else
	error 'FreeNAS build FAILED; please check above log for more details'
fi
