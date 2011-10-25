#!/bin/sh
#
# Copy this somewhere else and edit to your heart's content.
#

branch=trunk
clean=true
cvsup_host=cvsup1.freebsd.org
tmpdir=/dev/null

setup() {
	export PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin
	export SHELL=/bin/sh

	tmpdir=$(mktemp -d build.XXXXXXXX)
	pull $tmpdir
}

cleanup() {
	sudo rm -Rf $tmpdir
}

pull() {
	svn co https://freenas.svn.sourceforge.net/svnroot/freenas/$branch $1
}

# scp image <user>,freenas@frs.sourceforge.net:/home/frs/project/f/fr/freenas/<dir>
post_images() {
	# No-op
}

while getopts 'A:b:c:t:' optch; do
	case "$optch" in
	A)
		case "$OPTARG" in
		amd64|i386)
			;;
		*)
			echo "${0##*/}: ERROR: unknown architecture: $OPTARG"
			;;
		esac
		;;
	b)
		branch=$OPTARG
		;;
	c)
		cvsup_host=$OPTARG
		;;
	C)
		clean=false
		;;
	*)
		echo "${0##*/}: ERROR: unhandled/unknown option: $optch"
		exit 1
		;;
	esac
done

setup || exit $?
# Build
if sudo env FREEBSD_CVSUP_HOST=$cvsup_host sh build/do_build.sh; then
	post_images
else
	clean=false
fi
if $clean; then
	cleanup
fi
