#!/bin/sh
#
# Ensure the user can't downgrade their software.
#
# southdb proportedly supports downgrades, but that functionality doesn't
# work as expected [today], and causes support headaches because then database
# schema isn't migrated properly.
#
# The final result is that the newer schema sticks, whereas the old one
# doesn't.
#
# XXX: this is probably a bug with how we're handling southdb :).
#
# Garrett Cooper, March 2012

# 0 - NEW == OLD
# 1 - OLD < NEW
# 2 - OLD > NEW

compare_version \
	$OLD_AVATAR_VERSION \
	$NEW_AVATAR_VERSION
ec=$?
case $ec in
0)
	# Versions are the same.
	;;
1)
	# Upgrade!
	;;
2)
	error "cannot downgrade software"
	;;
*)
	error "an unknown error occurred (exit code = $ec)"
	;;
esac
