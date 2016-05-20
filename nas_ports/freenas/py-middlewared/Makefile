PORTNAME=	middlewared
PORTVERSION=    ${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}
PKGNAMEPREFIX=  ${PYTHON_PKGNAMEPREFIX}

CATEGORIES=     freenas
VALID_CATEGORIES+= freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        FreeNAS Middleware Daemon

USES=		python
USE_PYTHON=	autoplist distutils
EXTRACT_ONLY=

WRKSRC?=/usr/nas_source/middlewared

checksum fetch:
	echo ${.TARGET} not needed because building direct

.include <bsd.port.mk>
