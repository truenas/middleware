#
# $FreeBSD$
# $Id$
#

PORTNAME=       freenas-10gui
PORTVERSION=    ${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=     freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        FreeNAS new UI

USE_XZ=		yes
USE_PYTHON=	yes
EXTRACT_ONLY=

RUN_DEPENDS=	node:${PORTSDIR}/www/node

WRKSRC=		/usr/freenas_src/gui
WRKDEPLOY=	/usr/freenas_gui

NO_BUILD = yes

PLIST=		${WRKDEPLOY}/gui-plist

MAKE_JOBS_UNSAFE=yes

ALL_TARGET=obj all

SUB_LIST+=	PYTHON_CMD=${PYTHON_CMD}

checksum fetch:
	echo ${.TARGET} not needed because building direct

pre-install:
	true

do-install:
	install ${WRKSRC}/etc/gui ${STAGEDIR}${PREFIX}/etc/rc.d/
	install ${WRKSRC}/sbin/gui ${STAGEDIR}${PREFIX}/sbin/
	cp -a ${WRKDEPLOY}/ ${STAGEDIR}${PREFIX}/www/gui/

.include <bsd.port.mk>
