#!/bin/sh
# Warden install script
PROGDIR="/usr/local/share/warden"

mkdir -p ${PROGDIR} >/dev/null 2>/dev/null

mkdir ${PROGDIR}/tmp >/dev/null 2>/dev/null
mkdir ${PROGDIR}/export >/dev/null 2>/dev/null

DIR=`dirname $0`
cd ${DIR}

cp bin/warden /usr/local/bin/warden
chmod 755 /usr/local/bin/warden

# Save existing settings 
if [ -e "/usr/local/etc/warden.conf" ] ; then
  NIC=`grep '^NIC:' /usr/local/etc/warden.conf | awk '{print $2}'`
  WTMP=`grep '^WTMP:' /usr/local/etc/warden.conf | awk '{print $2}'`
  JDIR=`grep '^JDIR:' /usr/local/etc/warden.conf | awk '{print $2}'`
  ONIC=`grep '^NIC:' conf/warden.conf`
  OWTMP=`grep '^WTMP:' conf/warden.conf`
  OJDIR=`grep '^JDIR:' conf/warden.conf`
fi

cp conf/warden.conf /usr/local/etc/warden.conf
chmod 644 /usr/local/etc/warden.conf

# Save the settings
if [ -n "$NIC" ] ; then
   sed -i '' "s|$ONIC|NIC: $NIC|g" /usr/local/etc/warden.conf
   sed -i '' "s|$OWTMP|WTMP: $WTMP|g" /usr/local/etc/warden.conf
   sed -i '' "s|$OJDIR|JDIR: $JDIR|g" /usr/local/etc/warden.conf
fi

if [ -d "${PROGDIR}/linux-installs" ] ; then
  rm -rf ${PROGDIR}/linux-installs
fi
cp -r linux-installs ${PROGDIR}

if [ -d "${PROGDIR}/scripts" ] ; then
  rm -rf ${PROGDIR}/scripts
fi

cp -r scripts ${PROGDIR}
chmod 755 ${PROGDIR}/scripts/backend/*

# Setup rc.d
cp scripts/rc.d/wardenrc /usr/local/etc/rc.d/wardenrc
chmod 755 /usr/local/etc/rc.d/wardenrc

cp agent.png ${PROGDIR}/
cp agent.png ${PROGDIR}/warden.png

mkdir ${PROGDIR}/bin >/dev/null 2>/dev/null

exit 0
