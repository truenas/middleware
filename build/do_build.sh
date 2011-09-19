#!/bin/sh
#
# Build (either from scratch or using cached files):
# 	sh build/do_build.sh
#
# Force a full rebuild:
#	sh build/do_build.sh -f
#
# Force an update and rebuild world:
#	sh build/do_build.sh -u -f
#
# Just pull/update the sources:
#	sh build/do_build.sh -B -u
#

usage() {
	echo "usage: ${0##*/} [-Bfu] [-- nanobsd-options]"
	exit 1
}

cd "$(dirname "$0")/.."

. build/nano_env
. build/functions.sh

BUILD=true
if [ -s ${NANO_OBJ}/_.iw ]; then
	FULL_BUILD=false
else
	FULL_BUILD=true
fi
MAKE_JOBS=$(( 2 * $(sysctl -n kern.smp.cpus) + 1 ))
if [ -f FreeBSD/supfile ]; then
	UPDATE=false
else
	UPDATE=true
fi
USE_UNIONFS=false

while getopts 'Bfj:uU' optch; do
	case "$optch" in
	B)
		info "will not build"
		BUILD=false
		;;
	f)
		FULL_BUILD=true
		;;
	j)
		if ! echo "$OPTARG" | egrep -q '^[[:digit:]]$' || [ $OPTARG -le 0 ]; then
			usage
		fi
		MAKE_JOBS=$OPTARG
		;;
	u)
		UPDATE=true
		;;
	U)
		# This is undocumented for a very good reason. Use CPUS=1 for
		# known stability if you wish to try this feature.
		cat <<EOF
By pressing enter you understand that this does the unionfs optimization not
work on all filesystems (e.g. UFS SUJ on 9.x-BETA*) with all -j values.
EOF
		read junk
		UPDATE=true
		USE_UNIONFS=true
		;;
	\?)
		usage
		;;
	esac
done
shift $(( $OPTIND - 1 ))

set -e

requires_root

if $USE_UNIONFS; then
	if ! kldstat -v | grep -q unionfs; then
		error "You must load the unionfs module before executing $0!"
	fi
	# System seizes up when using buildworld with -j values greater than 1
	# with UFS+SUJ on 9.0-BETA2 + unionfs; not sure about other
	# filesystems/versions of FreeBSD (yet)...
	if [ ${CPUS:-1} -gt 1 ]; then
		UNIONFS_UFS_DEADLOCK_HACK=true
	else
		UNIONFS_UFS_DEADLOCK_HACK=false
	fi
fi

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
	if $USE_UNIONFS; then
		if $UNIONFS_UFS_DEADLOCK_HACK; then
			# reduce potential for filesystem deadlocks
			sync; sync; sync
		fi
	else
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
fi

if $USE_UNIONFS; then
	# Use unionfs to manage local changes applied via patch to the source.
	#
	# This was born out of an annoyance with nuking the entire tree to get
	# a deterministic state and with other delightfully stupid hacks I
	# employed to deal with patches being auto-appended.
	#
	# Make modifications to $NANO_SRC and $NANO_PORTS, not the files under
	# $FREENAS_ROOT/FreeBSD/{src,ports} if you use this.

	for uniondir in $NANO_SRC $NANO_PORTS; do
		type=$(basename $uniondir)

		if $USE_UNIONFS; then
			md_dev_file=$FREENAS_ROOT/FreeBSD/md-dev.$type
			if [ -f "$md_dev_file" ]; then
				mdconfig -d -u "$(cat $md_dev_file)"
			fi
			rm -f $md_dev_file
		fi

		if [ -d $uniondir ]; then
			while mount | grep $uniondir; do
				umount $uniondir
			done
		fi
		rm -Rf $FREENAS_ROOT/FreeBSD/touched/$type
		mkdir -p $FREENAS_ROOT/FreeBSD/touched/$type
		if [ ! -d $uniondir ]; then
			mkdir -p $uniondir
		fi

		mount -t unionfs $FREENAS_ROOT/FreeBSD/$type $uniondir

		if $UNIONFS_UFS_DEADLOCK_HACK; then
			mdconfig -a -t swap -s 32m > "$md_dev_file"
			md="/dev/$(cat "$md_dev_file")"
			newfs -O 1 -n -o time $md
			mount $md $FREENAS_ROOT/FreeBSD/touched/$type
		fi

		mount -t unionfs $FREENAS_ROOT/FreeBSD/touched/$type $uniondir
	done
fi

for patch in $(cd $FREENAS_ROOT/patches && ls freebsd-*.patch); do
	if $USE_UNIONFS; then
		echo "Applying patch $patch..."
		(cd $NANO_SRC && patch -E -p0 < $FREENAS_ROOT/patches/$patch)
	else
		if ! grep -q $patch $FREENAS_ROOT/FreeBSD/src-patches; then
			echo "Applying patch $patch..."
			(cd FreeBSD/src && patch -E -p0 < $FREENAS_ROOT/patches/$patch)
			echo $patch >> $FREENAS_ROOT/FreeBSD/src-patches
		fi
	fi
done
for patch in $(cd $FREENAS_ROOT/patches && ls ports-*.patch); do
	if $USE_UNIONFS; then
		echo "Applying patch $patch..."
		(cd $NANO_PORTS && patch -E -p0 < $FREENAS_ROOT/FreeBSD/patches/$patch)
	else
		if ! grep -q $patch $FREENAS_ROOT/FreeBSD/ports-patches; then
			echo "Applying patch $patch..."
			(cd FreeBSD/ports && patch -E -p0 < $FREENAS_ROOT/patches/$patch)
			echo $patch >> $FREENAS_ROOT/FreeBSD/ports-patches
		fi
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
# Make installworld a worthy sentinel for determining whether or not to
# rebuild things by default.
if ! "$FULL_BUILD"; then
	extra_args="-b"
fi
echo $NANO_SRC/tools/tools/nanobsd/nanobsd.sh $args $* $extra_args
if env MAKE_JOBS=$MAKE_JOBS sh $NANO_SRC/tools/tools/nanobsd/nanobsd.sh $args $* $extra_args; then
	xz -f ${NANO_OBJ}/_.disk.image
	mv ${NANO_OBJ}/_.disk.image.xz ${NANO_OBJ}/${NANO_IMGNAME}.xz
	sha256 ${NANO_OBJ}/${NANO_IMGNAME}.xz
else
	error 'FreeNAS build FAILED; please check above log for more details'
fi
