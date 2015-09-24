# Created by: William Grzybowski <wg@FreeBSD.org>
# $FreeBSD: head/sysutils/py-cdmi/Makefile 397691 2015-09-24 14:16:30Z wg $

PORTNAME=	cdmi
PORTVERSION=	1.0
CATEGORIES=	sysutils python
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}

MAINTAINER=	wg@FreeBSD.org
COMMENT=	CDMI on OpenStack Swift implementation

LICENSE=	APACHE20
LICENSE_FILE=	${WRKSRC}/LICENSE

RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}swift>0:${PORTSDIR}/databases/py-swift \
		${PYTHON_PKGNAMEPREFIX}webob>0:${PORTSDIR}/www/py-webob

USE_GITHUB=	yes
GH_ACCOUNT=	osaddon
GH_TAGNAME=	f0e3ad9

USES=		python
USE_PYTHON=	autoplist distutils

.include <bsd.port.mk>
