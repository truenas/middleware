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

BUILD_DEPENDS= ${PYTHON_PKGNAMEPREFIX}fastentrypoints>0:devel/py-fastentrypoints@${FLAVOR}
RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}ws4py>0:www/py-ws4py@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}aiohttp>0:www/py-aiohttp@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}aiohttp-wsgi>0:www/py-aiohttp-wsgi@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}Flask>0:www/py-flask@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}boto3>0:devel/py-boto3@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}netif>0:net/py-netif@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}bsd>0:freenas/py-bsd@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}raven>0:devel/py-raven@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}markdown>0:textproc/py-markdown@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}mako>0:textproc/py-mako@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}psutil>0:sysutils/py-psutil@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}libzfs>0:devel/py-libzfs@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}netsnmpagent>0:devel/py-netsnmpagent@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}pydevd>0:devel/py-pydevd@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}zeroconf>0:net/py-zeroconf@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}google-cloud-storage>0:www/py-google-cloud-storage@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}azure-storage>0:www/py-azure-storage@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}influxdb>0:databases/py-influxdb@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}asyncssh>0:security/py-asyncssh@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}croniter>0:sysutils/py-croniter@${FLAVOR} \
		rclone>0:net/rclone \
		swagger-ui>0:freenas/swagger-ui

USE_RC_SUBR=	middlewared

WRKSRC?=/usr/nas_source/middlewared

checksum fetch:
	echo ${.TARGET} not needed because building direct

.include <bsd.port.mk>
