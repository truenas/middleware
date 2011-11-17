#!/bin/sh
#
# Copy this somewhere else and edit to your heart's content.
#
# Space added in places to avoid potential merge conflicts.
#

# Values you shouldn't change.

clean=true
# Define beforehand to work around shell bugs.
postdir=/dev/null
tmpdir=/dev/null

# Values you can and should change.

branch=trunk
cvsup_host=cvsup1.freebsd.org
default_archs="amd64 i386"
postdir_base=/dev/null
tmpdir_template=e2e-bld.XXXXXXXX

setup() {
	export PATH=/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin
	export SHELL=/bin/sh

	tmpdir=$(realpath "$(mktemp -d $tmpdir_template)")
	chmod 0755 $tmpdir
	pull $tmpdir
	cd $tmpdir
	if [ -d "$postdir_base" ]; then
		postdir="$postdir_base/$(env LC_LANG=C date '+%m-%d-%Y')"
		mkdir -p "$postdir"
	else
		postdir=
	fi
}

cleanup() {
	sudo rm -Rf $tmpdir
}

pull() {

	svn co https://freenas.svn.sourceforge.net/svnroot/freenas/$branch $1

}

post_images() {
	(cd obj.$arch
	 release=$(ls *$arch.iso | sed -e "s/-$arch.*//g")
	 if [ "${RELEASE_BUILD:-}" = yes ]; then
		cp ../ReleaseNotes README
		set -- *.iso *.xz README
	 else
		set -- *.iso *.xz
	 fi
	 for file in $*; do
		sudo sh -c "sha256 $img > $img.sha256.txt"

		if [ -d "$postdir" ]; then
			cp $file* "$postdir"/.
		fi

		scp -o BatchMode=yes $img* \
		    yaberauneya,freenas@frs.sourceforge.net:/home/frs/project/f/fr/freenas/FreeNAS-8-nightly

	done)
}

while getopts 'A:b:c:t:' optch; do
	case "$optch" in
	A)
		_arch=
		for arch in $default_archs; do
			if [ "$arch" = "$OPTARG" ]; then
				_arch=$OPTARG
				break
			fi
		done
		if [ -z "$_arch" ]; then
			echo "${0##*/}: ERROR: unknown architecture: $OPTARG"
			exit 1
		fi
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
	cd /; cleanup
fi
