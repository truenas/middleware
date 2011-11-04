#!/bin/sh
#
# See README for up to date usage examples.
#

cd "$(dirname "$0")/.."

. build/nano_env
. build/functions.sh

# Should we build?
BUILD=true
# 0 - build only what's required (src, ports, diskimage, etc).
# 1 - force src build.
# 2 - nuke obj.* and build from scratch.
if [ -s ${NANO_OBJ}/_.ik -a -s ${NANO_OBJ}/_.iw ]; then
	FORCE_BUILD=0
else
	FORCE_BUILD=2
fi
# Number of jobs to pass to make. Only applies to src so far.
MAKE_JOBS=$(( 2 * $(sysctl -n kern.smp.cpus) + 1 ))
# Should we update src + ports?
if [ -f $FREENAS_ROOT/FreeBSD/.pulled ]; then
	UPDATE=false
else
	UPDATE=true
fi

usage() {
	cat <<EOF
usage: ${0##*/} [-Bfu] [-j make-jobs] [-- nanobsd-options]

-B - don't build. Will pull the sources and show you the nanobsd.sh invocation
     string instead. 
-f - if not specified, will pass either -b (if prebuilt) to nanobsd.sh, or
     nothing if not prebuilt. If specified once, force a
     buildworld / buildkernel (passes -n to nanobsd). If specified twice, this
     won't pass any options to nanobsd.sh, which will force a pristine build.
-j - number of make jobs to run; defaults to $MAKE_JOBS.
-u - force an update via csup (warning: there are potential issues with
     newly created files via patch -- use with caution).
EOF
	exit 1
}

while getopts 'Bfj:u' optch; do
	case "$optch" in
	B)
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
if $BUILD; then
	requires_root
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
	# Force a repatch because csup pulls pristine sources.
	: > $FREENAS_ROOT/FreeBSD/src-patches
	: > $FREENAS_ROOT/FreeBSD/ports-patches
	# Nuke the newly created files to avoid build errors, as
	# patch(1) will automatically append to the previously
	# non-existent file.
	for file in $(find $FREENAS_ROOT/FreeBSD/ -name '*.orig' -size 0); do
		rm -f "$(echo "$file" | sed -e 's/.orig//')"
	done
	: > $FREENAS_ROOT/FreeBSD/.pulled
fi

for patch in $(cd $FREENAS_ROOT/patches && ls freebsd-*.patch); do
	if ! grep -q $patch $FREENAS_ROOT/FreeBSD/src-patches; then
		echo "Applying patch $patch..."
		(cd FreeBSD/src &&
		 patch -C -p0 < $FREENAS_ROOT/patches/$patch &&
		 patch -E -p0 < $FREENAS_ROOT/patches/$patch)
		echo $patch >> $FREENAS_ROOT/FreeBSD/src-patches
	fi
done
for patch in $(cd $FREENAS_ROOT/patches && ls ports-*.patch); do
	if ! grep -q $patch $FREENAS_ROOT/FreeBSD/ports-patches; then
		echo "Applying patch $patch..."
		(cd FreeBSD/ports &&
		 patch -C -p0 < $FREENAS_ROOT/patches/$patch &&
		 patch -E -p0 < $FREENAS_ROOT/patches/$patch)
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

# OK, now we can build
cd $NANO_SRC
args="-c ${NANO_CFG_BASE}/freenas-common"
if [ $FORCE_BUILD -eq 0 ]; then
	extra_args="$extra_args -b"
elif [ $FORCE_BUILD -eq 1 ]; then
	extra_args="$extra_args -n"
fi
cmd="$FREENAS_ROOT/build/nanobsd/nanobsd.sh $args $* $extra_args -j $MAKE_JOBS"
echo $cmd
if ! $BUILD; then
	exit 0
fi
if sh $cmd; then
	echo "$NANO_LABEL build PASSED"
else
	error "$NANO_LABEL build FAILED; please check above log for more details"
fi
