#
# $FreeBSD$
# $Id$
#

PORTNAME=       pc-sysinstall
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=     freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        FreeNAS pc-sysinstall

USE_XZ=		yes

PREFIX=/

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
	:

do-install:
	mkdir -p ${STAGEDIR}/${PREFIX}/rescue
	make -C ${WRKSRC}/pc-sysinstall install DESTDIR=${STAGEDIR}/${PREFIX} NO_MAN=t

.include <bsd.port.mk>
