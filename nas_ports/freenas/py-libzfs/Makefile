#
# $FreeBSD$
# $Id$
#

PORTNAME=      	libzfs
PORTVERSION=    ${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}
PKGNAMEPREFIX=  ${PYTHON_PKGNAMEPREFIX}

CATEGORIES=     freenas
VALID_CATEGORIES+= freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        Python libzfs bindings

BUILD_DEPENDS=	

USE_XZ=		yes
USE_PYTHON=	yes
EXTRACT_ONLY=
BUILD_DEPENDS=  ${LOCALBASE}/bin/cython:${PORTSDIR}/lang/cython

WRKSRC=		/usr/freenas_src/py-libzfs

USES=		python:2
USE_PYTHON=	autoplist distutils

export FREEBSD_SRC=/usr/src

checksum fetch:
	echo ${.TARGET} not needed because building direct

.include <bsd.port.mk>
