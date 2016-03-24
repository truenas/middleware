# $FreeBSD$

PORTNAME=	freenas-pkgtools
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}
CATEGORIES=	freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=	dev@ixsystems.com
COMMENT=	FreeNAS sef\'s pkg tools

PRODUCT?=

EXTRACT_ONLY=
WRKSRC=/usr/nas_source/freenas-pkgtools

# no checksum, we just used git!
checksum fetch:
	${ECHO_CMD} ${.TARGET} not needed because building direct

ALL_TARGET=obj all

MAKE_JOBS_UNSAFE=yes

.include <bsd.port.mk>
