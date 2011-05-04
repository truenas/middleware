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
# This script does not tolerate any errors.
#

# Configurable
PREFIX=/tmp/servicepack

if [ $# != 2 ]; then
	echo Usage: $0 release-image new-image
	echo Note: both images needs to be raw and not compressed with xz
	exit 1
fi

echo -n "Clearing out and recreating working directory at ${PREFIX}... "
rm -fr ${PREFIX}
mkdir -p ${PREFIX}
echo "Done!"

echo -n "Creating vnode-based mds... "

# Original image
MD1=`mdconfig -a -t vnode -f $1`

# Latest image
MD2=`mdconfig -a -t vnode -f $2`

echo "Done!"

echo -n "Mounting mds... "

# Trees to mount
rm -fr ${PREFIX}/release ${PREFIX}/patched ${PREFIX}/servicepack
mkdir -p ${PREFIX}/release ${PREFIX}/patched
mkdir -p ${PREFIX}/servicepack

# Mount images at mountpoints
mount -o rdonly /dev/${MD1}a ${PREFIX}/release
mount -o rdonly /dev/${MD2}a ${PREFIX}/patched

echo "Done!"

echo -n "Computing SHA256 checksums... "

# Generate sha256 checksums
cd ${PREFIX}/release
find . | sort > ${PREFIX}/release.files
find . -type f | sort | xargs sha256 > ${PREFIX}/release.sha256

cd ${PREFIX}/patched
find . | sort > ${PREFIX}/patched.files
find . -type f | sort | xargs sha256 > ${PREFIX}/patched.sha256

comm -23 ${PREFIX}/release.files ${PREFIX}/patched.files > ${PREFIX}/removed.list
comm -13 ${PREFIX}/release.sha256 ${PREFIX}/patched.sha256 | cut -c9- | rev | cut -c69- | rev > ${PREFIX}/changed.list

echo "Done!"

echo -n "Copying changed files... "

tar cf - -T ${PREFIX}/changed.list | tar xf - -C ${PREFIX}/servicepack

echo "Done!"

echo -n "Generating post-install files... "

mkdir -p ${PREFIX}/servicepack/etc/servicepack
cp ${PREFIX}/release/etc/version.freenas ${PREFIX}/servicepack/etc/servicepack/version.expected

POSTINSTALL=${PREFIX}/servicepack/etc/servicepack/post-install

echo '#!/bin/sh' > ${POSTINSTALL}
echo 'mount -uw /' >> ${POSTINSTALL}
echo 'rm -f /etc/servicepack/version.expected' >> ${POSTINSTALL}

sed -e 's/^/rm -fr /' ${PREFIX}/removed.list >> ${POSTINSTALL}

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
mdconfig -d -u `echo ${MD1} | cut -c3-`
umount -f ${PREFIX}/patched
mdconfig -d -u `echo ${MD2} | cut -c3-`

echo "Done!"

echo "All done!  If you want to make any changes to the service pack as a"
echo "post-install action, change ${POSTINSTALL} then:"
echo

cat << E*O*F
	rm -f ${PREFIX}/servicepack.tar.xz
	cd ${PREFIX}
	tar cf servicepack.tar -C ${PREFIX}/servicepack .
	xz -9ve servicepack.tar
E*O*F

echo
echo "To re-roll the service pack."
