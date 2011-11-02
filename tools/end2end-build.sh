#!/bin/sh
#
# Copy this somewhere else and edit to your heart's content.
#
# Space added in places to avoid potential merge conflicts.
#

# Values you shouldn't change.

clean=true
# Define beforehand to work around shell bugs.
tmpdir=/dev/null

# Values you can and should change.

branch=trunk
cvsup_host=cvsup1.freebsd.org
default_archs="amd64 i386"

setup() {
	export PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin
	export SHELL=/bin/sh

	tmpdir=$(mktemp -d e2e-bld.XXXXXXXX)
	chmod 0755 $tmpdir
	pull $tmpdir
	cd $tmpdir
}

cleanup() {
	sudo rm -Rf $tmpdir
}

pull() {

	svn co https://freenas.svn.sourceforge.net/svnroot/freenas/$branch $1

}

post_images() {
	(cd obj.$arch
	 for img in *.iso *.xz; do
		sudo sh -c "sha256 $img > $img.sha256.txt"

		scp -o BatchMode=yes $img* \
		    yaberauneya,freenas@frs.sourceforge.net:/home/frs/project/f/fr/freenas/FreeNAS-8-nightly

	done)
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
		archs="$archs $OPTARG"
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

: ${archs=$default_archs}

set -e
setup
set +e

for arch in $archs; do

	# Build
	BUILD="env FREEBSD_CVSUP_HOST=$cvsup_host sh build/do_build.sh"
	# Build twice so the resulting image is smaller than the fat image
	# required for producing ports.
	# XXX: this should really be done in the nanobsd files to only have to
	# do this once, but it requires installing world twice.
	if sudo sh -c "export FREENAS_ARCH=$arch; $BUILD -- -fi && $BUILD"; then
		post_images
	else
		clean=false
	fi

done
if $clean; then
	cleanup
fi
