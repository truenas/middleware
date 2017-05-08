#!/bin/sh

PATH="${PATH}:/usr/local/bin:/usr/local/sbin"
export PATH

/usr/local/bin/alertcli.py > /tmp/.alert-health
if [ $? -ne 0 ] ; then
   exit 1
fi

have_alert=0

while read line
do
  echo $line | grep -q "^OK"
  if [ $? -eq 0 ] ; then
	continue
  fi
  echo "$line"
  have_alert=1
done < /tmp/.alert-health
rm /tmp/.alert-health

if [ $have_alert -eq 0 ] ; then
  echo "No Alerts"
  exit 0
else
  exit 1
fi
