# Created by: antoine@FreeBSD.org
# $FreeBSD$

PORTNAME=	karellen-geventws
PORTVERSION=	1.0.2.dev20161215225056

CATEGORIES=	www python
MASTER_SITES=	CHEESESHOP
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}

MAINTAINER=	antoine@FreeBSD.org
COMMENT=	WebSocket library for the gevent networking library

LICENSE=	APACHE20
LICENSE_FILE=	${WRKSRC}/LICENSE

RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}gevent>=0:${PORTSDIR}/devel/py-gevent

USES=		python
USE_PYTHON=	distutils autoplist

.include <bsd.port.mk>
