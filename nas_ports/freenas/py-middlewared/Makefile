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

BUILD_DEPENDS= ${PYTHON_PKGNAMEPREFIX}fastentrypoints>0:devel/py-fastentrypoints@${PY_FLAVOR}
RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}ws4py>0:www/py-ws4py@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}aiohttp>0:www/py-aiohttp@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}aiohttp-wsgi>0:www/py-aiohttp-wsgi@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}Flask>0:www/py-flask@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}boto3>0:www/py-boto3@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}netif>0:net/py-netif@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}bsd>0:freenas/py-bsd@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}raven>0:devel/py-raven@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}markdown>0:textproc/py-markdown@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}mako>0:textproc/py-mako@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}psutil>0:sysutils/py-psutil@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}libzfs>0:devel/py-libzfs@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}netsnmpagent>0:net/py-netsnmpagent@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}pydevd>0:devel/py-pydevd@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}zeroconf>0:net/py-zeroconf@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}influxdb>0:databases/py-influxdb@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}asyncssh>0:security/py-asyncssh@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}croniter>0:sysutils/py-croniter@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}bidict>0:devel/py-bidict@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}markdown2>0:textproc/py-markdown2@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}acme>0:security/py-acme@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}josepy>0:security/py-josepy@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}certbot-dns-cloudflare>0:security/py-certbot-dns-cloudflare@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}certbot-dns-digitalocean>0:security/py-certbot-dns-digitalocean@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}certbot-dns-google>0:security/py-certbot-dns-google@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}certbot-dns-ovh>0:security/py-certbot-dns-ovh@${PY_FLAVOR} \
		rclone>0:net/rclone \
		ifstat>0:net/ifstat \
		swagger-ui>0:freenas/swagger-ui

USE_RC_SUBR=	middlewared

WRKSRC?=/usr/nas_source/middlewared

checksum fetch:
	echo ${.TARGET} not needed because building direct

.include <bsd.port.mk>
