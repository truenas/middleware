#!/bin/sh
#
# Build (either from scratch or using cached files):
# 	sh build/do_build.sh
#
# Force a full rebuild (ports and source):
#	sh build/do_build.sh -ff
#
# Force an update and rebuild FreeBSD (world and kernel):
#	sh build/do_build.sh -u -f
#
# Just pull/update the sources:
#	sh build/do_build.sh -B -u
#

cd "$(dirname "$0")/.."

. build/nano_env
. build/functions.sh

BUILD=true
if [ -s ${NANO_OBJ}/_.iw -a -s ${NANO_OBJ}/_.ik ]; then
	FORCE_BUILD=0
else
	FORCE_BUILD=2
fi
MAKE_JOBS=$(( 2 * $(sysctl -n kern.smp.cpus) + 1 ))
if [ -f FreeBSD/supfile ]; then
	UPDATE=false
else
	UPDATE=true
fi

usage() {
	cat <<EOF
usage: ${0##*/} [-Bfu] [-j make-jobs] [-- nanobsd-options]

-j defaults to $MAKE_JOBS
EOF
	exit 1
}

while getopts 'Bfj:u' optch; do
	case "$optch" in
	B)
		info "will not build"
		BUILD=false
		;;
	f)
		: $(( FORCE_BUILD += 1 ))
		;;
	j)
		echo $OPTARG | egrep -q '^[[:digit:]]+$' && [ $OPTARG -le 0 ]
		if [ $? -ne 0 ]; then
			usage
		fi
		MAKE_JOBS=$OPTARG
		;;
	u)
		UPDATE=true
		;;
	\?)
		usage
		;;
	esac
done
shift $(( $OPTIND - 1 ))

set -e

requires_root

if $UPDATE; then
	if [ -z "$FREEBSD_CVSUP_HOST" ]; then
		error "No sup host defined, please define FREEBSD_CVSUP_HOST and rerun"
	fi
	echo "Checking out tree from ${FREEBSD_CVSUP_HOST}..."

	mkdir -p $FREENAS_ROOT/FreeBSD

	SUPFILE=$FREENAS_ROOT/FreeBSD/supfile
	cat <<EOF > $SUPFILE
*default host=${FREEBSD_CVSUP_HOST}
*default base=$FREENAS_ROOT/FreeBSD/sup
*default prefix=$FREENAS_ROOT/FreeBSD
*default release=cvs
*default delete use-rel-suffix
*default compress

src-all tag=RELENG_8_2
ports-all date=2011.07.17.00.00.00
EOF
	csup -L 1 $SUPFILE
	# Force a repatch because csup pulls pristine sources.
	: > $FREENAS_ROOT/FreeBSD/src-patches
	: > $FREENAS_ROOT/FreeBSD/ports-patches
	# Nuke the newly created files to avoid build errors, as
	# patch(1) will automatically append to the previously
	# non-existent file.
	for file in $(find FreeBSD/ -name '*.orig' -size 0); do
		rm -f "$(echo "$file" | sed -e 's/.orig//')"
	done
fi

for patch in $(cd $FREENAS_ROOT/patches && ls freebsd-*.patch); do
	if ! grep -q $patch $FREENAS_ROOT/FreeBSD/src-patches; then
		echo "Applying patch $patch..."
		(cd FreeBSD/src && patch -E -p0 < $FREENAS_ROOT/patches/$patch)
		echo $patch >> $FREENAS_ROOT/FreeBSD/src-patches
	fi
done
for patch in $(cd $FREENAS_ROOT/patches && ls ports-*.patch); do
	if ! grep -q $patch $FREENAS_ROOT/FreeBSD/ports-patches; then
		echo "Applying patch $patch..."
		(cd FreeBSD/ports && patch -E -p0 < $FREENAS_ROOT/patches/$patch)
		echo $patch >> $FREENAS_ROOT/FreeBSD/ports-patches
	fi
done

# HACK: chmod +x the script because:
# 1. It's not in FreeBSD proper, so it will always be touched.
# 2. The mode is 0644 by default, and using a pattern like ${SHELL}
#    in the Makefile snippet won't work with csh users because the
#    script uses /bin/sh constructs.
if [ -f "$NANO_SRC/include/mk-osreldate.sh.orig" ]; then
	chmod +x $NANO_SRC/include/mk-osreldate.sh
fi

if ! $BUILD; then
	exit 0
fi

# OK, now we can build
cd $NANO_SRC
args="-c ${NANO_CFG_BASE}/freenas-common"
if [ $FORCE_BUILD -eq 0 ]; then
	extra_args="-b"
elif [ $FORCE_BUILD -eq 1 ]; then
	extra_args="-n"
else
	extra_args=""
fi
echo $FREENAS_ROOT/build/nanobsd/nanobsd.sh $args $* $extra_args -j $MAKE_JOBS
sh $FREENAS_ROOT/build/nanobsd/nanobsd.sh $args $* $extra_args -j $MAKE_JOBS
if [ $? -eq 0 ]; then
	xz -f ${NANO_OBJ}/_.disk.image
	mv ${NANO_OBJ}/_.disk.image.xz ${NANO_OBJ}/${NANO_IMGNAME}.xz
	sha256 ${NANO_OBJ}/${NANO_IMGNAME}.xz
else
	error "$NANO_LABEL build FAILED; please check above log for more details"
fi
