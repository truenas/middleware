#
# $FreeBSD$
# $Id$
#

PORTNAME=       pcbsd-pbi
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
	mkdir -p /usr/pbi
	${MAKE} -C ${WRKSRC}/pcbsd/pbi-wrapper obj
	${MAKE} -C ${WRKSRC}/pcbsd/pbi-wrapper all

do-install:
	mkdir -p ${STAGEDIR}${PREFIX}/usr/pbi
	${MAKE} -C ${WRKSRC}/pcbsd/pbi-wrapper BINDIR=${STAGEDIR}${PREFIX}/usr/pbi install
	#
	# Adding pbi-manager
	#
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/sbin
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/pbi-manager/pbi-manager ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_add
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_addrepo
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_browser
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_autobuild
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_delete
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_deleterepo
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_icon
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_info
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_indextool
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_listrepo
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_makepatch
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_makeport
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_makerepo
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_metatool
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_patch
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_update
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_update_hashdir
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbid
	ln -f ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi_create ${STAGEDIR}${PREFIX}/usr/local/sbin/pbi-crashhandler
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/share/pcbsd/distfiles
	${INSTALL_DATA} ${WRKSRC}/pcbsd/pbi-manager/repo/pcbsd.rpo ${STAGEDIR}${PREFIX}/usr/local/share/pcbsd/distfiles/pcbsd.rpo
	#
	# Adding pc-extractoverlay
	#
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/bin
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/etc
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/share/pcbsd/conf
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/share/pcbsd/distfiles
	${INSTALL_SCRIPT} ${WRKSRC}/pcbsd/pc-extractoverlay/pc-extractoverlay ${STAGEDIR}${PREFIX}/usr/local/bin/pc-extractoverlay
	${INSTALL_DATA} ${WRKSRC}/pcbsd/pc-extractoverlay/server-excludes ${STAGEDIR}${PREFIX}/usr/local/share/pcbsd/conf
	${INSTALL_DATA} ${WRKSRC}/pcbsd/pc-extractoverlay/server-overlay/usr/local/etc/pkg-pubkey.cert ${STAGEDIR}${PREFIX}/usr/local/etc
	tar -c -v -J -f ${STAGEDIR}${PREFIX}/usr/local/share/pcbsd/distfiles/server-overlay.txz -C ${WRKSRC}/pcbsd/pc-extractoverlay/server-overlay .

.include <bsd.port.mk>
