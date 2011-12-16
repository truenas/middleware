#!/bin/sh

# interface:
# cd to top of tree
# sh ./build/do_build.sh
# magic happens :)
#

cd "$(dirname "$0")/.."

export root=$(pwd)
export FREENAS_ROOT=$root
: ${FREENAS_ARCH=$(uname -p)}
export NANO_LABEL="FreeNAS"
export FREENAS_ARCH
export NANO_CFG_BASE=$FREENAS_ROOT/nanobsd
export NANO_SRC=$FREENAS_ROOT/FreeBSD/src
export NANO_OBJ=${root}/obj.${FREENAS_ARCH}
PREP_SOURCE=${PREP_SOURCE:-""}

. build/functions.sh

# Make sure we have FreeBSD dirs
if [ ! -d FreeBSD ]; then
    mkdir FreeBSD
    mkdir FreeBSD/src
    mkdir FreeBSD/ports
fi
set -e

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
*default compress

src-all tag=RELENG_8_2
ports-all date=2011.07.17.00.00.00
EOF
	# Nuke the newly created files to avoid build errors.
	#
	# patch(1) will automatically append to the previously non-existent
	# file, which causes problems with .c, .h, .s, etc files.
	#
	# Do this here before running csup because it will pave over all files
	# that were previously added via a patch if it turns out that a change
	# was rolled into src or ports.
	for file in $(find $FREENAS_ROOT/FreeBSD -name '*.orig' -size 0); do
		rm -f "$(echo $file | sed -e 's/.orig$//')"
	done
    csup -L 1 ${root}/FreeBSD/supfile
	# Force a repatch because csup pulls pristine sources.
	: > $FREENAS_ROOT/FreeBSD/src-patches
	: > $FREENAS_ROOT/FreeBSD/ports-patches
fi

for patch in $(cd $FREENAS_ROOT/patches && ls freebsd-*.patch); do
	if ! grep -q $patch $FREENAS_ROOT/FreeBSD/src-patches; then
		echo "Applying patch $patch..."
		(cd FreeBSD/src &&
		 patch -C -p0 < $FREENAS_ROOT/patches/$patch &&
		 patch -E -p0 -s < $FREENAS_ROOT/patches/$patch)
		echo $patch >> $FREENAS_ROOT/FreeBSD/src-patches
	fi
done
for patch in $(cd $FREENAS_ROOT/patches && ls ports-*.patch); do
	if ! grep -q $patch $FREENAS_ROOT/FreeBSD/ports-patches; then
		echo "Applying patch $patch..."
		(cd FreeBSD/ports &&
		 patch -C -p0 < $FREENAS_ROOT/patches/$patch &&
		 patch -E -p0 -s < $FREENAS_ROOT/patches/$patch)
		echo $patch >> $FREENAS_ROOT/FreeBSD/ports-patches
	fi
done

if [ -n "${PREP_SOURCE}" ]; then
    exit
fi

# OK, now we can build
cd FreeBSD/src
args="-c ../../nanobsd/freenas-common"
: ${MAKE_JOBS=$(( 2 * $(sysctl -n kern.smp.cpus) + 1 ))}
args="$args -j $MAKE_JOBS"
if [ `whoami` != "root" ]; then
    echo "You must be root to run this"
    exit 1
fi
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
echo $FREENAS_ROOT/build/nanobsd/nanobsd.sh $args $extra_args
if sh "$FREENAS_ROOT/build/nanobsd/nanobsd.sh" $args $extra_args; then
	echo "$NANO_LABEL build PASSED"
else
	error "$NANO_LABEL build FAILED; please check above log for more details"
fi
