#
# $FreeBSD$
# $Id$
#

PORTNAME=       freenas-files
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=     freenas
VALID_CATEGORIES+=	freenas

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
	${MAKE} -C ${WRKSRC}/extract-tarball   obj
	${MAKE} -C ${WRKSRC}/extract-tarball  all
	${MAKE} -C ${WRKSRC}/winacl   obj
	${MAKE} -C ${WRKSRC}/winacl  all

do-install:
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/bin
	${MAKE} -C ${WRKSRC}/extract-tarball  BINDIR=${STAGEDIR}${PREFIX}/usr/local/bin install
	${MAKE} -C ${WRKSRC}/winacl  BINDIR=${STAGEDIR}${PREFIX}/usr/local/bin install
	#
	# Adding autotune
	#
	${INSTALL_SCRIPT} ${WRKSRC}/autotune/files/autotune.py ${STAGEDIR}${PREFIX}/usr/local/bin/autotune

.include <bsd.port.mk>
