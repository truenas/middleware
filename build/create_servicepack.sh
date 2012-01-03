#!/bin/sh
#-
# Copyright (c) 2011 iXsystems, Inc., All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#
# Intended for use internally only to make 'service pack' style images.
#

MD1=
MD2=
PREFIX=

cleanup() {
	trap - EXIT
	for md in $MD1 $MD2; do
		umount /dev/$md
		mdconfig -d -u $md
	done || :
	rm -Rf $PREFIX
}

AVATAR_ROOT="$(realpath "$(dirname "$0")/..")"
. "$AVATAR_ROOT/build/nano_env"
. "$AVATAR_ROOT/build/functions.sh"

requires_root

if [ $# != 2 ]; then
	cat <<EOF
usage: ${0##*/} release-image new-image
both images needs to be raw and not compressed with xz
EOF
	exit 1
fi

RELEASE_IMAGE=$1
NEW_IMAGE=$2

set -e

echo -n "Creating temporary working directory... "

PREFIX=$(mktemp -d servicepack.XXXXXX)
trap cleanup EXIT

echo "Done!"

echo -n "Creating vnode-based mds... "

# Original image
MD1=`mdconfig -a -t vnode -f "$RELEASE_IMAGE"`

# Latest image
MD2=`mdconfig -a -t vnode -f "$NEW_IMAGE"`

echo "Done!"

echo -n "Mounting mds... "

# Trees to mount
rm -rf ${PREFIX}/release ${PREFIX}/patched ${PREFIX}/servicepack
mkdir -p ${PREFIX}/release ${PREFIX}/patched ${PREFIX}/servicepack

# Mount images at mountpoints
mount -o ro /dev/${MD1}s1a ${PREFIX}/release
mount -o ro /dev/${MD2}s1a ${PREFIX}/patched

echo "Done!"

echo -n "Computing SHA256 checksums... "

# Generate sha256 checksums
for dir in release patched; do
	cd ${PREFIX}/$dir
	find . | sort > ${PREFIX}/$dir.files
	find . -type f | sort | xargs sha256 > ${PREFIX}/$dir.sha256
done

comm -23 ${PREFIX}/release.files ${PREFIX}/patched.files > ${PREFIX}/removed.list
comm -13 ${PREFIX}/release.sha256 ${PREFIX}/patched.sha256 | cut -c9- | rev | cut -c69- | rev > ${PREFIX}/changed.list.tmp
grep ^\./conf/base/ ${PREFIX}/changed.list.tmp | cut -c12- | sed -e s/^/./ > ${PREFIX}/changed.list.exclude
comm -23 ${PREFIX}/changed.list.tmp ${PREFIX}/changed.list.exclude > ${PREFIX}/changed.list
rm -f ${PREFIX}/changed.list.tmp ${PREFIX}/changed.list.exclude

echo "Done!"

echo -n "Copying changed files... "

tar cf - -T ${PREFIX}/changed.list | tar xf - -C ${PREFIX}/servicepack

echo "Done!"

echo -n "Generating post-install files... "

mkdir -p ${PREFIX}/servicepack/etc/servicepack
VERSION_FILE=$(find ${PREFIX}/release/etc -name 'version*')
cp $VERSION_FILE ${PREFIX}/servicepack/etc/servicepack/version.expected

POSTINSTALL=${PREFIX}/servicepack/etc/servicepack/post-install

echo '#!/bin/sh' > ${POSTINSTALL}
echo 'mount -uw /' >> ${POSTINSTALL}
echo 'rm -f /etc/servicepack/version.expected' >> ${POSTINSTALL}

sed -e 's/^/rm -rf /' ${PREFIX}/removed.list >> ${POSTINSTALL}

echo '# All changes to firmware volume must be done before this line'
echo 'mount -ur /' >> ${POSTINSTALL}

chmod +x ${POSTINSTALL}

echo "Done!"

echo "Packing the service pack... "

rm -f ${PREFIX}/servicepack.tar.xz
cd ${PREFIX}
tar cf servicepack.tar -C ${PREFIX}/servicepack .
xz -9ve servicepack.tar

echo -n "Unmounting and destroying md devices... "

umount -f ${PREFIX}/release
mdconfig -d -u $MD1
umount -f ${PREFIX}/patched
mdconfig -d -u $MD2

mv "$NEW_IMAGE_TMP" "$NEW_IMAGE"

echo "Done!"

cat <<EOF
All done!  If you want to make any changes to the service pack as a
post-install action, change ${POSTINSTALL} then execute:

	rm -f ${PREFIX}/servicepack.tar.xz
	cd ${PREFIX}
	tar --options xz:compression-level=9 -cJpf - -C ${PREFIX}/servicepack.xz .

To re-roll the service pack.
EOF
