#!/bin/sh

mydir=`dirname $0`
#set -x
gui_error_log=`mktemp -t install_worker.gui_error_log`
verbose_log=`mktemp -t install_worker.verboselog`
usage_log=`mktemp -t install_worker.usage_log`
sh $mydir/install_worker2.sh ${1+"$@"} 3>$gui_error_log 2>$verbose_log 4>$usage_log
ec=$?
#if [ $ec -ne 0 ] ; then
    cat $gui_error_log 1>&2
#fi
if [ -s $usage_log ] ; then
    cat $usage_log
fi
#    cat $usage_log
rm $usage_log
exit $ec
