#
# $FreeBSD$
# $Id$
#

PORTNAME=       SMART
PORTVERSION=    ${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=   ${REVISION}
PKGNAMEPREFIX=  ${PYTHON_PKGNAMEPREFIX}

CATEGORIES=     freenas
VALID_CATEGORIES+= freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        Python wrapper for `smartctl` (smartmontools)

BUILD_DEPENDS=	
RUN_DEPENDS=	smartctl:${PORTSDIR}/sysutils/smartmontools

USES=		python
EXTRACT_ONLY=

WRKSRC=		/usr/freenas_src/py-SMART

USES=		python:2
USE_PYTHON=	autoplist distutils

checksum fetch:
	echo ${.TARGET} not needed because building direct

.include <bsd.port.mk>
