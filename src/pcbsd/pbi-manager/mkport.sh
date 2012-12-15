#!/bin/sh
# Make files to update FreeBSD Port

ver=`cat port-files/Makefile | grep PORTVERSION | cut -d '=' -f 2 | tr -d '\t'`

# Make the distfile
mkdir /tmp/pbi-manager-${ver}

tar cvf - --exclude .svn INSTALL Makefile install.sh pbi-manager etc icons man1 man5 man8 module-examples rc.d repo 2>/dev/null| tar xvf - -C /tmp/pbi-manager-${ver} 2>/dev/null
tar cvjf pbi-manager-${ver}.tar.bz2 -C /tmp pbi-manager-${ver} 2>/dev/null
rm -rf /tmp/pbi-manager-${ver}

echo "Distfile: pbi-manager-${ver}.tar.bz2"

# Make the distinfo file
sha256=`sha256 -q pbi-manager-${ver}.tar.bz2`
size=`ls -ALln pbi-manager-${ver}.tar.bz2 | awk '{print $5}'`

echo "SHA256 (pbi-manager-${ver}.tar.bz2) = ${sha256}
SIZE (pbi-manager-${ver}.tar.bz2) = ${size}" > port-files/distinfo

tar cvzf port-$ver.tgz --exclude .svn -C port-files . 2>/dev/null
echo "Port Files: port-$ver.tgz"
