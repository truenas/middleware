# Created by: Peter Schuller <peter.schuller@infidyne.com>
# $FreeBSD$

PORTNAME=	gevent
PORTVERSION=	1.1.1
PORTREVISION=	2
CATEGORIES=	devel python
MASTER_SITES=	CHEESESHOP
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}

MAINTAINER=	sunpoet@FreeBSD.org
COMMENT=	Python co-routine networking library based on greenlet

LICENSE=	MIT
LICENSE_FILE=	${WRKSRC}/LICENSE

LIB_DEPENDS=	libcares.so:${PORTSDIR}/dns/c-ares \
		libev.so:${PORTSDIR}/devel/libev
RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}greenlet>=0.4.7:${PORTSDIR}/devel/py-greenlet
TEST_DEPENDS=	${PYTHON_PKGNAMEPREFIX}greenlet>=0.4.7:${PORTSDIR}/devel/py-greenlet \
		${PYTHON_PKGNAMEPREFIX}sqlite3>=0:${PORTSDIR}/databases/py-sqlite3

DO_MAKE_TEST=	${SETENV} PYTHONPATH=../ ${PYTHON_CMD}
MAKE_ENV=	CARES_EMBED=0 LIBEV_EMBED=0
TEST_TARGET=	testrunner.py
TEST_WRKSRC=	${WRKSRC}/greentest
USE_PYTHON=	autoplist distutils
USES=		localbase python

post-install:
	${STRIP_CMD} ${STAGEDIR}${PYTHON_SITELIBDIR}/gevent/*.so

.include <bsd.port.mk>
