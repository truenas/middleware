#
# $FreeBSD$
# $Id$
#

PORTNAME=       pcbsd-warden
PORTVERSION=    1.0
PORTREVISION=   ${REVISION}

CATEGORIES=     freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        miscellaneous files for FreeNAS

USE_XZ=		yes

PREFIX=/

# explicitly set this for the port build
FREEBSD_SRCTOP=/usr/src
PLIST_SUB=	MACHINE_ARCH=${MACHINE_ARCH}

EXTRACT_ONLY=
WRKSRC=/usr/freenas_src

# no checksum, we just used git!
 #extract:
checksum fetch:
	echo ${.TARGET} not needed because building direct

pre-clean:
	@

ALL_TARGET=obj all

MAKE_JOBS_UNSAFE=yes

do-build:
	@

do-install:
	#
	# Adding warden
	#
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/etc
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/etc/rc.d
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/bin
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/share/warden
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/share/warden/tmp
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/share/warden/export
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/rc.d
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/share/warden/bin
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/hooks
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/share/warden/linux-installs
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/bin/warden ${STAGEDIR}${PREFIX}/usr/local/bin/warden
	${INSTALL_DATA} ${WRKSRC}/pcbsd/warden/pluginjail-packages ${STAGEDIR}${PREFIX}/usr/local/share/warden/pluginjail-packages
	${INSTALL_DATA} ${WRKSRC}/pcbsd/warden/pcbsd-utils-packages ${STAGEDIR}${PREFIX}/usr/local/share/warden/pcbsd-utils-packages
	${INSTALL_DATA} ${WRKSRC}/pcbsd/warden/conf/warden.conf ${STAGEDIR}${PREFIX}/usr/local/etc/warden.conf
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/linux-installs/debian-6-squeeze ${STAGEDIR}${PREFIX}/usr/local/share/warden/linux-installs/debian-6-squeeze
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/linux-installs/gentoo-stage3-i486 ${STAGEDIR}${PREFIX}/usr/local/share/warden/linux-installs/gentoo-stage3-i486
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/checkstatus.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/checkstatus.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/checkupdates.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/checkupdates.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/chrootjail.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/chrootjail.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/createjail.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/createjail.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/createtemplate.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/createtemplate.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/cronsnap.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/cronsnap.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/deletejail.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/deletejail.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/details.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/details.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/exportjail.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/exportjail.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/functions.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/functions.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/importjail.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/importjail.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/jailid.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/jailid.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/listjails.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/listjails.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/listpbis.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/listpbis.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/listpkgs.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/listpkgs.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/setupusers.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/setupusers.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/startjail.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/startjail.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/stopjail.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/stopjail.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/zfsclonesnap.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/zfsclonesnap.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/zfscronsnap.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/zfscronsnap.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/zfslistclone.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/zfslistclone.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/zfslistsnap.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/zfslistsnap.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/zfsmksnap.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/zfsmksnap.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/zfsrevertsnap.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/zfsrevertsnap.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/zfsrmclone.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/zfsrmclone.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/backend/zfsrmsnap.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/backend/zfsrmsnap.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/hooks/dhclient-exit-hooks ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/hooks/dhclient-exit-hooks
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/rc.d/shutdown.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/rc.d/shutdown.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/rc.d/startup.sh ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/rc.d/startup.sh
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/rc.d/wardenrc ${STAGEDIR}${PREFIX}/usr/local/share/warden/scripts/rc.d/wardenrc
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/warden/scripts/rc.d/wardenrc ${STAGEDIR}${PREFIX}/usr/local/etc/wardenrc
	${INSTALL_DATA} ${WRKSRC}/pcbsd/warden/agent.png ${STAGEDIR}${PREFIX}/usr/local/share/warden/agent.png
	${INSTALL_DATA} ${WRKSRC}/pcbsd/warden/agent.png ${STAGEDIR}${PREFIX}/usr/local/share/warden/warden.png
	#
	# Adding pcbsd mirrors
	#
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/share/pcbsd/conf
	${INSTALL_DATA} ${WRKSRC}/pcbsd/xtrafiles/local/share/pcbsd/conf/iso-mirror ${STAGEDIR}${PREFIX}/usr/local/share/pcbsd/conf/iso-mirror
	${INSTALL_DATA} ${WRKSRC}/pcbsd/xtrafiles/local/share/pcbsd/conf/pbi-mirror ${STAGEDIR}${PREFIX}/usr/local/share/pcbsd/conf/pbi-mirror
	${INSTALL_DATA} ${WRKSRC}/pcbsd/xtrafiles/local/share/pcbsd/conf/pcbsd-mirrors ${STAGEDIR}${PREFIX}/usr/local/share/pcbsd/conf/pcbsd-mirrors
	${INSTALL_DATA} ${WRKSRC}/pcbsd/xtrafiles/local/share/pcbsd/conf/pkg-mirror ${STAGEDIR}${PREFIX}/usr/local/share/pcbsd/conf/pkg-mirror
	${INSTALL_DATA} ${WRKSRC}/pcbsd/xtrafiles/local/share/pcbsd/conf/update-mirror ${STAGEDIR}${PREFIX}/usr/local/share/pcbsd/conf/update-mirror
	#
	# Adding pcbsd libsh
	#
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/share/pcbsd/scripts
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/libsh/functions.sh ${STAGEDIR}${PREFIX}/usr/local/share/pcbsd/scripts/functions.sh

.include <bsd.port.mk>
