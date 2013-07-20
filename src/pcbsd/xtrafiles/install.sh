#!/bin/sh

# Copy files to system
tar cvf - -C local . 2>/dev/null | tar xvf - -C /usr/local
if [ $? -ne 0 ] ; then
  exit 1
fi

exit 0
