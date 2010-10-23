#!/bin/sh -x

# interface:
# cd to top of tree
# sh ./build/do_build.sh
# magic happens :)
#

root=$(pwd)
: ${FREENAS_ARCH=$(uname -p)}
export FREENAS_ARCH
export NANO_OBJ=${root}/obj.${FREENAS_ARCH}

# Make sure we have FreeBSD dirs
if [ ! -d FreeBSD ]; then
    mkdir FreeBSD
    mkdir FreeBSD/src
    mkdir FreeBSD/ports
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

src-all tag=RELENG_8_1_0_RELEASE
ports-all tag=RELEASE_8_1_0
EOF
    csup -L 1 ${root}/FreeBSD/supfile
# cvsup fixes any changes we make, it seems.  Repatch
    rm -f ${root}/FreeBSD/src-patches
    rm -f ${root}/FreeBSD/ports-patches
fi

# Make sure that all the patches are applied
touch ${root}/FreeBSD/src-patches
for i in $(cd ${root}/patches && echo freebsd-*); do
    if ! grep $i ${root}/FreeBSD/src-patches > /dev/null 2>&1; then
	echo "Applying patch $i..."
	(cd FreeBSD/src && patch -p0 < ${root}/patches/$i)
	echo $i >> ${root}/FreeBSD/src-patches
    fi
done
touch ${root}/FreeBSD/ports-patches
for i in $(cd ${root}/patches && echo ports-*); do
    if ! grep $i ${root}/FreeBSD/ports-patches > /dev/null 2>&1; then
	echo "Applying patch $i..."
	(cd FreeBSD/ports && patch -p0 < ${root}/patches/$i)
	echo $i >> ${root}/FreeBSD/ports-patches
    fi
done

# OK, now we can build
cd FreeBSD/src
args="-c ../../nanobsd/freenas-common"
if [ `whoami` != "root" ]; then
    echo "You must be root to run this"
    exit 1
fi
echo tools/tools/nanobsd/nanobsd.sh $args $*
sh tools/tools/nanobsd/nanobsd.sh $args $*
