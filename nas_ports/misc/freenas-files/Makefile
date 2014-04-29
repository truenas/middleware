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

.include <bsd.port.mk>
