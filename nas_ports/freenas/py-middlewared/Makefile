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

BUILD_DEPENDS= ${PYTHON_PKGNAMEPREFIX}fastentrypoints>0:devel/py-fastentrypoints
RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}ws4py>0:www/py-ws4py \
		${PYTHON_PKGNAMEPREFIX}aiohttp>0:www/py-aiohttp \
		${PYTHON_PKGNAMEPREFIX}aiohttp-wsgi>0:www/py-aiohttp-wsgi \
		${PYTHON_PKGNAMEPREFIX}Flask>0:www/py-flask \
		${PYTHON_PKGNAMEPREFIX}boto3>0:devel/py-boto3 \
		${PYTHON_PKGNAMEPREFIX}netif>0:net/py-netif \
		${PYTHON_PKGNAMEPREFIX}bsd>0:freenas/py-bsd \
		${PYTHON_PKGNAMEPREFIX}raven>0:devel/py-raven \
		${PYTHON_PKGNAMEPREFIX}markdown>0:textproc/py-markdown \
		${PYTHON_PKGNAMEPREFIX}mako>0:textproc/py-mako \
		${PYTHON_PKGNAMEPREFIX}psutil>0:sysutils/py-psutil \
		rclone>0:net/rclone

USE_RC_SUBR=	middlewared

WRKSRC?=/usr/nas_source/middlewared

checksum fetch:
	echo ${.TARGET} not needed because building direct

.include <bsd.port.mk>
