#!/bin/sh
#
# Unpack the servicepack payload.
#
# Garrett Cooper, March 2012

# XXX: make this more atomic

cd /
tar xpf $SCRIPTDIR/payload.tar
