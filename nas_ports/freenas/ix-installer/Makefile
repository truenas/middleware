# $FreeBSD$

PORTNAME=	ix-installer
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}

CATEGORIES=	freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=	dev@ixsystems.com
COMMENT=	FreeNAS installer

PRODUCT?=
USE_XZ=		yes

EXTRACT_ONLY=
WRKSRC=		/usr/nas_source/ix-installer
USES=		python
USE_PYTHON=	autoplist distutils

# no checksum, we just used git!
checksum fetch:
	${ECHO_CMD} ${.TARGET} not needed because building direct

.include <bsd.port.mk>
