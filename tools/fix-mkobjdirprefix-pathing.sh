#!/bin/sh
#
# This script takes a working FreeNAS SDK directory tree (sources vs obj.*
# directories) and moves it over to its proper spot if things are out of
# synch. This is needed because...
#
# 1. MKOBJDIRPREFIX is built up in a canonical manner (see
#    BW_CANONICALOBJDIR in src/Makefile for more details).
# 2. Some tools hardcode paths into sourcefiles (cpp, crunchgen, flex,
#    etc).
# 3. symlinks to absolute paths get broken when moved.
#
# The fact that this script doesn't explicitly call rm -Rf and is limited to
# the obj.* directory was designed to safeguard against accidentally hosing a
# system.
#
# Please modify this script with care.
#
# XXX: this script by itself does not make a tree portable. More hacking needs
# to go into the FreeBSD base system (hint: cpp is the biggest offender) in
# order to make this a reality.
#
# NOTES:
# So far, what's been learned, is...
# 1. That you must issue another buildworld to fix things (nanobsd.sh -n helps).
# 2. buildkernel will fail when running mkdep on some modules, and also fail
#    'silently' (complains on the console) with missing headers messages with
#    some modules. Might be mkdep again or config.

set -e

NEW_MKOBJDIRPREFIX=$(echo "$(realpath "$NANO_OBJ")$NANO_SRC" | sed -e 's,/+,/,g')
if [ -d "$NEW_MKOBJDIRPREFIX" ]; then
	# The directory already exists as expected; no change required
	echo "${0##*/}: INFO: path already exists (no change required)"
	exit 0
fi
# Find ${MKOBJDIRPREFIX} but not its descendants.
OLD_MKOBJDIRPREFIX=$(find "$NANO_OBJ" -type d -name src | grep /FreeBSD/src | grep -v /FreeBSD/src/)

if [ "$OLD_MKOBJDIRPREFIX" = "$NEW_MKOBJDIRPREFIX" ]; then
	# Nothing to change :).
	echo "${0##*/}: INFO: directories are the same."
	exit 0
elif [ ! -d "$OLD_MKOBJDIRPREFIX" ]; then
	# New build tree.
	echo "${0##*/}: INFO: didn't find a FreeBSD obj directory."
	exit 0
fi

cd "$NANO_OBJ"

mkdir -p "$(dirname "$NEW_MKOBJDIRPREFIX")"
mv "$OLD_MKOBJDIRPREFIX" "$NEW_MKOBJDIRPREFIX"
# Prune the orphaned directory tree.
while [ "$OLD_MKOBJDIRPREFIX" != "$NANO_OBJ" ]; do
	if ! rmdir "$(dirname $OLD_MKOBJDIRPREFIX)" 2>/dev/null; then
		break
	fi
	OLD_MKOBJDIRPREFIX=$(dirname "$OLD_MKOBJDIRPREFIX")
done
if [ -d "$OLD_MKOBJDIRPREFIX" -a "$OLD_MKOBJDIRPREFIX" != "$NANO_OBJ" ]; then
	# Inform the user that the directory has junk in it still to prevent
	# infinite loops.
	echo "${0##*/}: ERROR: there are orphaned files in the old MKOBJDIRPREFIX ($OLD_MKOBJDIRPREFIX)"
	exit 1
fi
