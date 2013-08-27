#!/bin/sh
#
# Automatically run the builds, keep some logs, and wipe our backside
#
# nightly.sh depends:		devel/git, net/rsync
# FreeNAS depends:		lang/python, sysutils/cdrtools

PATH=/sbin:/bin:/usr/sbin:/usr/bin:/usr/local/sbin:/usr/local/bin

set -x

FREENAS_GIT="file:///freenas-build/freenas.git"
FREENAS_BRANCH="master"
GIT_REPO="file:///freenas-build/trueos.git"
GIT_PORTS_REPO="file:///freenas-build/ports.git"
MASTER_SITE_OVERRIDE='http://localhost/freenas/ports-distfiles/${DIST_SUBDIR}/'

# Update repos
(
cd $(echo ${FREENAS_GIT}|sed "s,file://,,")
git fetch
cd $(echo ${GIT_REPO}|sed "s,file://,,")
git fetch
cd $(echo ${GIT_PORTS_REPO}|sed "s,file://,,")
git fetch
)

RE=jpaetzel		# Local release engineer account
SFRE=jpaetzel		# The RE user's SourceForge account

TONIGHT=$(/bin/date -ju +"%Y-%m-%d")

ZPOOL=tank
ZPREFIX=/${ZPOOL}		# Assume ZFS is not root
LOGPATH=home/${RE}/nightly_logs
ZLOGPATH=${ZPREFIX}/${LOGPATH}/${TONIGHT}
BUILDPATH=build/nightlies
ZBUILDPATH=${ZPREFIX}/${BUILDPATH}/${TONIGHT}
NANO_LABEL=FreeNAS
VERSION=9.2.0-ALPHA

SHARE=/freenas
ARCHIVE=${SHARE}/BSD/releng/FreeNAS/nightlies

# Ensure that our archives are mounted
/bin/df ${SHARE} | /usr/bin/grep -q ${SHARE} || /sbin/mount ${SHARE}

# Prep log dir
/bin/mkdir -p ${ZLOGPATH} || exit

# Pre-clean logs and obsolete builds after 30 days
/usr/bin/find ${ZPREFIX}/${LOGPATH} -type d -maxdepth 1 -mtime +30d \
	-exec /bin/rm -r '{}' \;
/usr/bin/find ${ARCHIVE} -type d -maxdepth 1 -mtime +30d \
	-exec /bin/rm -r '{}' \;

# Clean up old build environments after 5 days

# Problem: We can find old directories, but we have to divine the actual ZFS
# ZFS path. This isn't easy to do sanely since mount point names and poolsi
# can be arbitray. We do know the name of the pool and the path to the build
# datasets, so pull out only the names of the data sets (yyyy-mm-dd) and then
# append the ZFS path to pass on to `destroy`.
for build in `/usr/bin/find ${ZPREFIX}/${BUILDPATH} -type d -maxdepth 1 \
	 -mtime +5 | /usr/bin/awk -F "/" '{print $NF}'`; do
	/sbin/zfs destroy ${ZPOOL}/${BUILDPATH}/${build}
done

# Create and populate build environment
/sbin/zfs create -p ${ZPOOL}/${BUILDPATH}/${TONIGHT}
/usr/local/bin/git clone -b ${FREENAS_BRANCH} --depth 1 ${FREENAS_GIT} ${ZBUILDPATH} 2>&1 > \
	${ZLOGPATH}/checkout.log || exit

# Locate to top level of working clone and force checkout
cd ${ZBUILDPATH} || exit
/usr/bin/env \
	GIT_REPO=${GIT_REPO} GIT_PORTS_REPO=${GIT_PORTS_REPO} \
	MASTER_SITE_OVERRIDE=${MASTER_SITE_OVERRIDE} \
	NANO_LABEL=${NANO_LABEL} VERSION=${VERSION} \
	/bin/sh build/do_build.sh -B 2>&1 >> \
	${ZLOGPATH}/checkout.log || exit

# FIXME
# This is to prevent 'debugfs' from eating the build box.
# This has been applied in freenas/ports github
#patch -p0 -d ${ZBUILDPATH}/FreeBSD/ports/ -i /root/e2fsprogs_notest.diff

# Begin building targets
/usr/bin/env \
	GIT_REPO=${GIT_REPO} GIT_PORTS_REPO=${GIT_PORTS_REPO} \
	MASTER_SITE_OVERRIDE=${MASTER_SITE_OVERRIDE} \
	FREENAS_ARCH=amd64 \
	NANO_LABEL=${NANO_LABEL} VERSION=${VERSION} \
	/bin/sh build/do_build.sh \
	-t os-base -z 2>&1 > ${ZLOGPATH}/amd64.log
/usr/bin/env \
	GIT_REPO=${GIT_REPO} GIT_PORTS_REPO=${GIT_PORTS_REPO} \
	MASTER_SITE_OVERRIDE=${MASTER_SITE_OVERRIDE} \
	FREENAS_ARCH=amd64 \
	NANO_LABEL=${NANO_LABEL} VERSION=${VERSION} \
	/bin/sh build/do_build.sh \
	-a 2>&1 > ${ZLOGPATH}/amd64.log
/usr/bin/env FREENAS_ARCH=amd64 /bin/sh build/create_iso.sh \
	NANO_LABEL=${NANO_LABEL} VERSION=${VERSION} \
	2>&1 >> ${ZLOGPATH}/amd64.log || exit

/usr/bin/env \
	GIT_REPO=${GIT_REPO} GIT_PORTS_REPO=${GIT_PORTS_REPO} \
	MASTER_SITE_OVERRIDE=${MASTER_SITE_OVERRIDE} \
	FREENAS_ARCH=i386 \
	NANO_LABEL=${NANO_LABEL} VERSION=${VERSION} \
	/bin/sh build/do_build.sh \
	-t os-base -z 2>&1 > ${ZLOGPATH}/i386.log
/usr/bin/env \
	GIT_REPO=${GIT_REPO} GIT_PORTS_REPO=${GIT_PORTS_REPO} \
	MASTER_SITE_OVERRIDE=${MASTER_SITE_OVERRIDE} \
	FREENAS_ARCH=i386 \
	NANO_LABEL=${NANO_LABEL} VERSION=${VERSION} \
	/bin/sh build/do_build.sh \
	-a 2>&1 > ${ZLOGPATH}/i386.log
/usr/bin/env FREENAS_ARCH=i386 /bin/sh build/create_iso.sh \
	NANO_LABEL=${NANO_LABEL} VERSION=${VERSION} \
	2>&1 >> ${ZLOGPATH}/i386.log || exit

set -x

# If we made it this far, start boxing the finished product
/bin/mkdir -p ${ZBUILDPATH}/sandbox/x64/plugins
/bin/cp ${ZBUILDPATH}/os-base/amd64/FreeNAS* ${ZBUILDPATH}/sandbox/x64
/bin/mkdir -p ${ZBUILDPATH}/sandbox/x86/plugins
/bin/cp ${ZBUILDPATH}/os-base/i386/FreeNAS* ${ZBUILDPATH}/sandbox/x86
for i in transmission minidlna firefly; do
	/bin/cp ${ZBUILDPATH}/${i}/amd64/*.pbi ${ZBUILDPATH}/sandbox/x64/plugins/
	/bin/cp ${ZBUILDPATH}/${i}/i386/*.pbi ${ZBUILDPATH}/sandbox/x86/plugins/
done

# Generate checksums for our build
for dist in `/usr/bin/find ${ZBUILDPATH}/sandbox -type f`; do
	/sbin/sha256 -q ${dist} > ${dist}.sha256.txt
done

/bin/mkdir -p ${ARCHIVE}/${TONIGHT} &&
/usr/local/bin/rsync -a ${ZBUILDPATH}/sandbox/ ${ARCHIVE}/${TONIGHT} \

# From here, we need to rsync to soureforge
/usr/local/bin/rsync -a -e "ssh -i /root/.ssh/freenas/nightlies.jpaetzel" \
	${ARCHIVE}/ \
	${SFRE}@frs.sourceforge.net:/home/frs/project/freenas/FreeNAS-nightlies/ \
