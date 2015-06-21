#
# $FreeBSD$
# $Id$
#

PORTNAME=       cam
PORTVERSION=    ${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=   ${REVISION}
PKGNAMEPREFIX=  ${PYTHON_PKGNAMEPREFIX}

CATEGORIES=     freenas
VALID_CATEGORIES+= freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        Python libcam wrapper

BUILD_DEPENDS=	

USES=		python
EXTRACT_ONLY=
BUILD_DEPENDS=  ${LOCALBASE}/bin/cython:${PORTSDIR}/lang/cython

WRKSRC=		/usr/freenas_src/py-cam

USES=		python:2
USE_PYTHON=	autoplist distutils

checksum fetch:
	echo ${.TARGET} not needed because building direct

.include <bsd.port.mk>
