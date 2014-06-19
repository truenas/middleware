#!/bin/sh
#
# Makes sure that the architecture is consistent across upgrades
#
# There are certain non-NAS critical items that break, like the reporting data)
# if you switch architectures (x86 <-> x64). In the future, if incompatible
# architectures are added (arm vs i386 vs mips vs powerpc), this would result
# in someone 'bricking' their machine.
#
# Garrett Cooper, March 2012

if [ "$OLD_AVATAR_ARCH" -a "$OLD_AVATAR_ARCH" != "$NEW_AVATAR_ARCH" ]
then
	error "architectures do not match ($OLD_AVATAR_ARCH != $NEW_AVATAR_ARCH)"
fi
