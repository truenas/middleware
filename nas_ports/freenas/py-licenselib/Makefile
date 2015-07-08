# $FreeBSD$

PORTNAME=	licenselib
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}
CATEGORIES=	freenas
VALID_CATEGORIES+=freenas

MAINTAINER=	wg@FreeBSD.org
COMMENT=	License library for FreeNAS/TrueNAS

FETCH_DEPENDS=	git:${PORTSDIR}/devel/git
RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}enum34>=:${PORTSDIR}/devel/py-enum34

USES=		python
USE_PYTHON=	autoplist distutils

EXTRACT_ONLY=
WRKSRC?=/usr/freenas_src/licenselib

# no checksum, we just used git!
 #extract:
checksum fetch:
	echo ${.TARGET} not needed because building direct


.include <bsd.port.mk>
