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

USES=		python
USE_PYTHON=	autoplist distutils
EXTRACT_ONLY=
BUILD_DEPENDS=  ${LOCALBASE}/bin/cython:${PORTSDIR}/lang/cython

WRKSRC?=/usr/nas_source/py-libzfs

MAKE_ENV=       FREEBSD_SRC=/usr/src TRUEOS=yes

checksum fetch:
	echo ${.TARGET} not needed because building direct

.include <bsd.port.mk>
