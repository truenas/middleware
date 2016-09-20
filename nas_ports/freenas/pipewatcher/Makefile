# $FreeBSD$

PORTNAME=	pipewatcher
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=	freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=	dev@ixsystems.com
COMMENT=	Pipe watcher to be used in replication

PRODUCT?=

EXTRACT_ONLY=
WRKSRC=/usr/nas_source/pipewatcher

# no checksum, we just used git!
checksum fetch:
	echo ${.TARGET} not needed because building direct

pre-clean:
	@

do-build:
	cd ${WRKSRC} && ${CC} pipewatcher.c -o pipewatcher

do-install:
	mkdir -p ${STAGEDIR}${PREFIX}/bin
	${INSTALL_PROGRAM} ${WRKSRC}/pipewatcher ${STAGEDIR}${PREFIX}/bin/

.include <bsd.port.mk>
