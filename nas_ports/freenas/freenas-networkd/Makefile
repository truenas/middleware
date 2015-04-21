#
# $FreeBSD$
# $Id$
#

PORTNAME=       freenas-networkd
PORTVERSION=    ${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=     freenas
VALID_CATEGORIES+= freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        FreeNAS network configuration daemon

USE_XZ=		yes
USE_PYTHON=	yes
EXTRACT_ONLY=

NO_BUILD= 	yes
MAKE_JOBS_UNSAFE= yes
ALL_TARGET=	obj all
WRKSRC=		/usr/freenas_src/networkd

USES=		python

checksum fetch:
	echo ${.TARGET} not needed because building direct

do-install:
	${MAKE} -C ${WRKSRC} install PREFIX=${STAGEDIR}${PREFIX} PYTHON=${PYTHON_CMD}

.include <bsd.port.mk>
