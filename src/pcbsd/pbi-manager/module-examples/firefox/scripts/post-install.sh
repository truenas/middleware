#!/bin/sh
#########################################

cat /boot/loader.conf | grep 'sem_load="YES"' >/dev/null 2>/dev/null
if [ "$?" != "0" ]
then
  echo 'sem_load="YES"' >>/boot/loader.conf
fi

kldload sem >/dev/null 2>/dev/null

