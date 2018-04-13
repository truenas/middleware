# $FreeBSD$

PORTNAME=	bsd
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}

CATEGORIES=	freenas
VALID_CATEGORIES+= freenas

MAINTAINER=	dev@ixsystems.com
COMMENT=	Python wrappers for various BSD interfaces

EXTRACT_ONLY=
BUILD_DEPENDS=  ${PYTHON_PKGNAMEPREFIX}six>0:devel/py-six@${FLAVOR}

WRKSRC=		/usr/nas_source/py-bsd

USES=		python
USE_PYTHON=	autoplist cython distutils

checksum fetch:
	${ECHO_CMD} ${.TARGET} not needed because building direct

.include <bsd.port.mk>
