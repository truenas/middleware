#
# $FreeBSD$
# $Id$
#

PORTNAME=       freenas-debug
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=     freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        FreeNAS debug utils

USE_XZ=		yes

PREFIX=/usr/local

EXTRACT_ONLY=
WRKSRC=/usr/freenas_src

# no checksum, we just used git!
checksum fetch:
	echo ${.TARGET} not needed because building direct

pre-clean:
	@

ALL_TARGET=obj all

MAKE_JOBS_UNSAFE=yes

do-build:
	@

do-install:
	mkdir -p ${STAGEDIR}${PREFIX}/libexec/freenas-debug
	cp -a ${WRKSRC}/freenas-debug/libexec/freenas-debug/ ${STAGEDIR}${PREFIX}/libexec/freenas-debug/
	${INSTALL_SCRIPT} ${WRKSRC}/freenas-debug/bin/freenas-debug ${STAGEDIR}${PREFIX}/bin/freenas-debug

.include <bsd.port.mk>
