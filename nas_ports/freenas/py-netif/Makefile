#
# $FreeBSD$
# $Id$
#

PORTNAME=       netif
PORTVERSION=    ${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=   ${REVISION}
PKGNAMEPREFIX=  ${PYTHON_PKGNAMEPREFIX}

CATEGORIES=     freenas
VALID_CATEGORIES+= freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        Python network configuration library

BUILD_DEPENDS=	

USE_XZ=		yes
USE_PYTHON=	yes
EXTRACT_ONLY=
BUILD_DEPENDS=  ${LOCALBASE}/bin/cython:${PORTSDIR}/lang/cython

WRKSRC=		/usr/nas_source2/py-netif

USES=		python:2
USE_PYTHON=	autoplist distutils

checksum fetch:
	echo ${.TARGET} not needed because building direct

.include <bsd.port.mk>
