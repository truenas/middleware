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

RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}gevent>0:${PORTSDIR}/devel/py-gevent \
		${PYTHON_PKGNAMEPREFIX}gevent-websocket>0:${PORTSDIR}/www/py-gevent-websocket \
		${PYTHON_PKGNAMEPREFIX}ws4py>0:${PORTSDIR}/www/py-ws4py \
		${PYTHON_PKGNAMEPREFIX}falcon>0:${PORTSDIR}/www/py-falcon \
		${PYTHON_PKGNAMEPREFIX}Flask>0:${PORTSDIR}/www/py-flask \
		${PYTHON_PKGNAMEPREFIX}boto3>0:${PORTSDIR}/devel/py-boto3 \
		rclone>0:${PORTSDIR}/net/rclone

USE_RC_SUBR=	middlewared

WRKSRC?=/usr/nas_source/middlewared

checksum fetch:
	echo ${.TARGET} not needed because building direct

.include <bsd.port.mk>
