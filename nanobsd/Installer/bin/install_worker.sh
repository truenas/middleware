#!/bin/sh

mydir=`dirname $0`
#set -x
gui_error_log=`mktemp -t /tmp/install.gui_error_log`
verbose_log=`mktemp -t /tmp/install.verboselog`
sh $mydir/install_worker2.sh ${1+"$@"} 3>$gui_error_log 2>$verbose_log
ec=$?
#if [ $ec -ne 0 ] ; then
    cat $gui_error_log 1>&2
#fi
exit $ec
