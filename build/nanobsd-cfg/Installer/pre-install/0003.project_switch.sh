#!/bin/sh
#
# Ensure the user can't install incompatible software.
#
# FreeNAS <-> TrueNAS, etc shouldn't be supported, nor should switching from a
# particular avatar project to another mutually incompatible avatar project
# (cyb0rg <-> FreeNAS).
#
# Garrett Cooper, March 2012
#

if [ "$OLD_AVATAR_PROJECT" -a "$OLD_AVATAR_PROJECT" != "$NEW_AVATAR_PROJECT" ]
then
	error "projects do not match ($OLD_AVATAR_PROJECT != $NEW_AVATAR_PROJECT)"
fi
