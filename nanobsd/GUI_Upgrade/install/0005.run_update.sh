#!/bin/sh
#
# Run the nanobsd updater with the fixed partition image.
#
# Garrett Cooper, March 2012

if [ "$VERBOSE" != "" -a "$VERBOSE" != "0" ] ; then
    sh -x $SCRIPTDIR/bin/update $SCRIPTDIR/firmware.img
else
    sh $SCRIPTDIR/bin/update $SCRIPTDIR/firmware.img
fi
