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
# Intended for use internally only to make 'hotpatch' style images.
#

MD1=
MD2=
PREFIX=

cleanup() {
	trap - EXIT
	for md in $MD1 $MD2
	do
		umount /dev/${md}s1a
		mdconfig -d -u $md
	done || :
}

AVATAR_ROOT="$(realpath "$(dirname "$0")/..")"
. "$AVATAR_ROOT/build/nano_env"
. "$AVATAR_ROOT/build/functions.sh"

requires_root

if [ $# -ne 2 ]
then
	cat <<EOF
usage: ${0##*/} old.img new.img
EOF
	exit 1
fi

OLD_IMAGE=$1
NEW_IMAGE=$2

set -e

echo -n "Creating temporary working directory... "

PREFIX=$(realpath "$(mktemp -d hp.XXXXXX)")
trap cleanup EXIT


echo "Done!"

echo -n "Creating vnode-based mds... "

# Original image
MD1=$(mdconfig -a -f "$OLD_IMAGE")

# Latest image
MD2=$(mdconfig -a -f "$NEW_IMAGE")

echo "Done!"

echo -n "Mounting mds... "

set -u

# NOTE: Do not add trailing slashes to these values ;)
OLD_DIR=$PREFIX/release
NEW_DIR=$PREFIX/patched
HP_DIR=$PREFIX/hotpatch

# Trees to mount
mkdir $OLD_DIR $NEW_DIR $HP_DIR

# Mount images at mountpoints
mount -o ro /dev/${MD1}s1a $OLD_DIR
mount -o ro /dev/${MD2}s1a $NEW_DIR

echo "Done!"

echo -n "Comparing old and new releases... "


for dir in $OLD_DIR $NEW_DIR
do
	(
	cd $dir
	find . | sort > $dir.files
	find . -type f -print0 | xargs -n 1 -0 sha256 | sort -k 2 > $dir.sha256
	)
done

comm -23 $OLD_DIR.files $NEW_DIR.files
comm -23 $OLD_DIR.files $NEW_DIR.files > $PREFIX/removed.list
comm -13 $OLD_DIR.sha256 $NEW_DIR.sha256 | cut -c9- | rev | cut -c69- | rev > \
    $PREFIX/changed.list.tmp
grep ^\./conf/base/ $PREFIX/changed.list.tmp | cut -c12- | sed -e s/^/./ > \
    $PREFIX/changed.list.exclude
comm -23 $PREFIX/changed.list.tmp $PREFIX/changed.list.exclude > \
    $PREFIX/changed.list
rm -f $PREFIX/changed.list.tmp $PREFIX/changed.list.exclude

echo "Done!"

echo -n "Copying changed files... "

(tar cf - -C $NEW_DIR -T $PREFIX/changed.list && : > $PREFIX/.copy-ok) | \
	tar xpf - -C $HP_DIR
[ -f ${PREFIX}/.copy-ok ]

echo "Done!"

echo -n "Generating post-install files... "

HP_SCRIPTS=$PREFIX/hp-scripts
INSTALL_SCRIPT_DIR="$HP_SCRIPTS/install"

mkdir -p $INSTALL_SCRIPT_DIR

# Installation cleanup script.
cat > $INSTALL_SCRIPT_DIR/0003.remove_old_files.sh <<EOF
#!/bin/sh
#
# Remove all files and directories which shouldn't be present in the image
# post-hotpatch installation.
#
# Garrett Cooper, March 2012

# XXX: what if the payload unpack fails?
EOF
sed -e 's/^\./rm -rf /' $PREFIX/removed.list >> \
	$INSTALL_SCRIPT_DIR/0003.remove_old_files.sh

echo "Done!"

echo -n "Packaging the hotpatch... "

MK_HOTPATCH=$PREFIX/mk_hotpatch.sh
cat > $MK_HOTPATCH <<EOF
#!/bin/sh

tar -cpJf $PREFIX/hotpatch.txz \\
	-C "$OLD_DIR/conf/base" \\
		etc/avatar.conf \\
	-C $AVATAR_ROOT/nanobsd/Installer \\
		. \\
	-C $AVATAR_ROOT/nanobsd/Hotpatch \\
		. \\
	-C $HP_SCRIPTS \\
		. \\
	-C $PREFIX \\
		payload.tar
EOF
tar -cpf $PREFIX/payload.tar -C $HP_DIR .
sh $MK_HOTPATCH 

echo "Done!"

echo -n "Unmounting and destroying md devices... "

cleanup

echo "Done!"

cat <<EOF
All done!

If you want to make any changes to the hotpatch, add your customizations to
\`$INSTALL_SCRIPT_DIR/0004.custom_hotpatch.sh', then execute
\`sh $MK_HOTPATCH' to re-roll the hotpatch.

EOF
