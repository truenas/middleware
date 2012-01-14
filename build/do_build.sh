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
if [ -f $AVATAR_ROOT/FreeBSD/.pulled ]; then
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

case "$-" in
*x*)
	trace="-x"
	;;
*)
	trace=
	;;
esac

set -e
if $BUILD; then
	requires_root
fi

if $UPDATE; then
	if [ -z "$FREEBSD_CVSUP_HOST" ]; then
		error "No sup host defined, please define FREEBSD_CVSUP_HOST and rerun"
	fi
	mkdir -p $AVATAR_ROOT/FreeBSD

	: ${FREEBSD_SRC_REPOSITORY_ROOT=http://svn.freebsd.org/base}
	FREEBSD_SRC_URL_REL="stable/8"

	FREEBSD_SRC_URL_FULL="$FREEBSD_SRC_REPOSITORY_ROOT/$FREEBSD_SRC_URL_REL"

	(
	 cd "$AVATAR_ROOT/FreeBSD"
	 if [ -d src/.svn ]; then
		svn upgrade src >/dev/null 2>&1 || :
	 	svn resolved src
	 else
		svn co $FREEBSD_SRC_URL_FULL src
	 fi
	 # Always do this so the csup pulled files are paved over.
 	 svn revert -R src
	 svn up src
	)

	SUPFILE=$AVATAR_ROOT/FreeBSD/supfile
	cat <<EOF > $SUPFILE
*default host=${FREEBSD_CVSUP_HOST}
*default base=$AVATAR_ROOT/FreeBSD/sup
*default prefix=$AVATAR_ROOT/FreeBSD
*default release=cvs
*default delete use-rel-suffix
*default compress

ports-all date=2011.12.28.00.00.00
EOF
	# Nuke newly created files to avoid build errors.
	svn_status_ok="$AVATAR_ROOT/FreeBSD/.svn_status_ok"
	rm -f "$svn_status_ok"
	(
	 svn status $AVATAR_ROOT/FreeBSD/src
	 : > "$svn_status_ok"
	) | \
		awk '$1 == "?" { print $2 }' | \
		xargs rm -Rf
	[ -f "$svn_status_ok" ]

	for file in $(find $AVATAR_ROOT/FreeBSD/ports -name '*.orig' -size 0); do
		rm -f "$(echo $file | sed -e 's/.orig$//')"
	done
	echo "Checking out ports tree from ${FREEBSD_CVSUP_HOST}..."
	csup -L 1 $SUPFILE
	# Force a repatch.
	: > $AVATAR_ROOT/FreeBSD/src-patches
	: > $AVATAR_ROOT/FreeBSD/ports-patches
	: > $AVATAR_ROOT/FreeBSD/.pulled
fi

_lp=last-patch.$$.log
for patch in $(cd $AVATAR_ROOT/patches && ls freebsd-*.patch); do
	if ! grep -q $patch $AVATAR_ROOT/FreeBSD/src-patches; then
		echo "Applying patch $patch..."
		(cd FreeBSD/src &&
		 patch -C -f -p0 < $AVATAR_ROOT/patches/$patch >$_lp 2>&1 ||
		 { echo "Failed to apply patch: $patch (check $(pwd)/$_lp)";
		   exit 1; } &&
		 patch -E -p0 -s < $AVATAR_ROOT/patches/$patch)
		echo $patch >> $AVATAR_ROOT/FreeBSD/src-patches
	fi
done
for patch in $(cd $AVATAR_ROOT/patches && ls ports-*.patch); do
	if ! grep -q $patch $AVATAR_ROOT/FreeBSD/ports-patches; then
		echo "Applying patch $patch..."
		(cd FreeBSD/ports &&
		 patch -C -f -p0 < $AVATAR_ROOT/patches/$patch >$_lp 2>&1 ||
		{ echo "Failed to apply patch: $patch (check $(pwd)/$_lp)";
		  exit 1; } &&
		 patch -E -p0 -s < $AVATAR_ROOT/patches/$patch)
		echo $patch >> $AVATAR_ROOT/FreeBSD/ports-patches
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
cmd="$AVATAR_ROOT/build/nanobsd/nanobsd.sh $args $* $extra_args -j $MAKE_JOBS"
echo $cmd
if ! $BUILD; then
	exit 0
fi
if sh $trace $cmd; then
	echo "$NANO_LABEL build PASSED"
else
	error "$NANO_LABEL build FAILED; please check above log for more details"
fi
