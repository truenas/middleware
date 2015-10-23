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
	:

do-install:
	mkdir -p ${STAGEDIR}${PREFIX}/usr/local/bin
	cp -a ${WRKSRC}/freenas/ ${STAGEDIR}${PREFIX}/

post-install:
	cd ${WRKSRC}/freenas && ${FIND} . -type f | \
		${SED} -e 's|^\./||' | ${SORT} >> ${TMPPLIST}


.include <bsd.port.mk>
