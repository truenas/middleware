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

error() {
	echo >&2 "${0##/*}: ERROR: $*"
	exit 1
}

usage() {
	echo "usage: ${0##*/} [-f ports|all] [-- nanobsd-options]"
	exit 1
}

cd "$(dirname "$0")/.."

FORCE_UPDATE=false
#FORCE_REBUILD_PORTS=false
FORCE_REBUILD_SRC=false

while getopts 'f:' optch; do
	case "$optch" in
	f)
		FORCE_UPDATE=true
		case "$OPTARG" in
		all)
			#FORCE_REBUILD_PORTS=true
			FORCE_REBUILD_SRC=true
			;;
		ports)
			#FORCE_REBUILD_PORTS=true
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
PREP_SOURCE=${PREP_SOURCE:-""}

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

src-all tag=RELENG_8_2
ports-all date=2011.07.17.00.00.00
EOF
	csup -L 1 FreeBSD/supfile
	# Force a repatch because csup pulls pristine sources.
	: > ${root}/FreeBSD/src-patches
	: > ${root}/FreeBSD/ports-patches

	# csup doesn't clean out non-existent files (diff -N) as there isn't a
	# corresponding VCS history. Nuke the newly created files to avoid build
	# errors, as patch(1) will automatically append to the previously
	# non-existent file.
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

if [ -n "${PREP_SOURCE}" ]; then
	exit
fi

# OK, now we can build
cd FreeBSD/src
args="-c ${root}/nanobsd/freenas-common"
if [ -d ${NANO_OBJ} ] && ! "$FORCE_REBUILD_SRC"; then
	extra_args="-b"
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
