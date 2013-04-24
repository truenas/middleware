#!/bin/sh

cp pc-extractoverlay /usr/local/bin/pc-extractoverlay
if [ $? -ne 0 ] ; then
  exit 1
fi
chmod 755 /usr/local/bin/pc-extractoverlay
if [ $? -ne 0 ] ; then
  exit 1
fi

if [ ! -d "/usr/local/share/pcbsd/conf" ] ; then
  mkdir -p /usr/local/share/pcbsd/conf
fi
if [ ! -d "/usr/local/share/pcbsd/distfiles" ] ; then
  mkdir -p /usr/local/share/pcbsd/distfiles
fi

# Copy port prune list
cp prune-port-files /usr/local/share/pcbsd/conf
if [ $? -ne 0 ] ; then
  exit 1
fi

# Copy exclude list
cp port-excludes /usr/local/share/pcbsd/conf
if [ $? -ne 0 ] ; then
  exit 1
fi
cp desktop-excludes /usr/local/share/pcbsd/conf
if [ $? -ne 0 ] ; then
  exit 1
fi
cp server-excludes /usr/local/share/pcbsd/conf
if [ $? -ne 0 ] ; then
  exit 1
fi

# Now create overlay.txz file
tar cvJf /usr/local/share/pcbsd/distfiles/port-overlay.txz -C ports-overlay .
if [ $? -ne 0 ] ; then
  exit 1
fi

# Now create desktop-overlay.txz file
tar cvJf /usr/local/share/pcbsd/distfiles/desktop-overlay.txz -C desktop-overlay .
if [ $? -ne 0 ] ; then
  exit 1
fi

# Now create server-overlay.txz file
tar cvJf /usr/local/share/pcbsd/distfiles/server-overlay.txz -C server-overlay .
if [ $? -ne 0 ] ; then
  exit 1
fi

exit 0
