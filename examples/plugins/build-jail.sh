#!/bin/sh

JAILDIR=/usr/pbistuff/plugins
mkdir -p $JAILDIR/dev
mkdir -p $JAILDIR/etc
mkdir -p $JAILDIR/usr/tmp
chmod 777 $JAILDIR/usr/tmp

SRCDIR=/usr/src
cd $SRCDIR

make installworld DESTDIR=$JAILDIR
cd $SRCDIR/etc
#cp /etc/resolv.conf $JAILDIR

make distribution DESTDIR=$JAILDIR 
cd $JAILDIR

touch $JAILDIR/etc/fstab
