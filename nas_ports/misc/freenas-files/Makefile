#
# $FreeBSD$
# $Id$
#

PORTNAME=       freenas-files
PORTVERSION=    1.0
#PORTREVISION=   1

CATEGORIES=     misc

MAINTAINER=     dev@ixsystems.com
COMMENT=        miscellaneous files for FreeNAS

USE_XZ=		yes

LOCALBASE=/

# explicitly set this for the port build
FREEBSD_SRCTOP=/usr/src
PLIST_SUB=	MACHINE_ARCH=${MACHINE_ARCH}

EXTRACT_ONLY=
WRKSRC=/usr/nas_source2

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
	${MAKE} -C ${WRKSRC}/extract-tarball   obj
	${MAKE} -C ${WRKSRC}/extract-tarball  all
	${MAKE} -C ${WRKSRC}/winacl   obj
	${MAKE} -C ${WRKSRC}/winacl  all

do-install:
	mkdir -p ${STAGEDIR}${PREFIX}/usr/pbi
	${MAKE} -C ${WRKSRC}/pcbsd/pbi-wrapper BINDIR=${STAGEDIR}${PREFIX}/usr/pbi install
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/bin
	${MAKE} -C ${WRKSRC}/extract-tarball  BINDIR=${STAGEDIR}${PREFIX}/usr/local/bin install
	${MAKE} -C ${WRKSRC}/winacl  BINDIR=${STAGEDIR}${PREFIX}/usr/local/bin install
	# Adding autotune
	${INSTALL_SCRIPT} ${WRKSRC}/autotune/files/autotune.py ${STAGEDIR}${PREFIX}/usr/local/bin/autotune
	# Adding pbi-manager
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


.include <bsd.port.mk>
