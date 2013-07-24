#!/bin/sh

if [ "$1" = "-b" -a "$2" != "" ] ; then
    GIT_BRANCH_ARG="-b $2"
    shift;shift
fi

OUTDIR=$1

git clone $GIT_BRANCH_ARG /freenas-build/freenas.git $OUTDIR
cd $OUTDIR 
git config  remote.origin.url git@github.com:freenas/freenas.git

