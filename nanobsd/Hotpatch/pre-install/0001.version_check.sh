#!/bin/sh
#
# Ensure that the hotpatch is built for the running system.
#
# Garrett Cooper, March 2012

# 0 - NEW == OLD
# 1 - OLD < NEW
# 2 - OLD > NEW

old_version="$OLD_AVATAR_VERSION-$OLD_AVATAR_BUILD_NUMBER"
new_version="$NEW_AVATAR_VERSION-$NEW_AVATAR_BUILD_NUMBER"

# XXX: won't work with git and its non-monotonically increasing revision hashes
compare_version \
	$old_version \
	$new_version
ec=$?
case $ec in
0)
	# Hotpatch is usable.
	;;
1|2)
	error "hotpatch not valid on this version of software ($old_version != $new_version)"
	;;
*)
	error "an unknown error occurred (exit code = $ec)"
	;;
esac
