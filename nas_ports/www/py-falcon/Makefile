# Created by: Zhihao Yuan <lichray@gmail.com>
# $FreeBSD: head/www/py-falcon/Makefile 412351 2016-04-01 14:33:55Z mat $

PORTNAME=	falcon
PORTVERSION=	1.0.0
CATEGORIES=	www python
MASTER_SITES=	CHEESESHOP
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}

MAINTAINER=	lichray@gmail.com
COMMENT=	High-performance Python framework for building cloud APIs

LICENSE=	APACHE20

BUILD_DEPENDS=	cython>=0.11.2:lang/cython
RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}testtools>=0:devel/py-testtools \
		${PYTHON_PKGNAMEPREFIX}six>=1.1.0:devel/py-six

USES=		python
USE_PYTHON=	distutils autoplist

.include <bsd.port.mk>
