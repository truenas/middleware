#
# $FreeBSD$
# $Id$
#

PORTNAME=       fnutils
PORTVERSION=    ${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=   ${REVISION}
PKGNAMEPREFIX=  ${PYTHON_PKGNAMEPREFIX}

CATEGORIES=     freenas
VALID_CATEGORIES+= freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        FreeNAS common Python modules

BUILD_DEPENDS=	

USE_XZ=		yes
USE_PYTHON=	yes
EXTRACT_ONLY=

WRKSRC=		/usr/nas_source2/py-fnutils

USES=		python:2
USE_PYTHON=	autoplist distutils

checksum fetch:
	echo ${.TARGET} not needed because building direct

.include <bsd.port.mk>
