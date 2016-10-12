# Created by: William Grzybowski <wg@FreeBSD.org>
# $FreeBSD: head/net/py-netif/Makefile 412348 2016-04-01 14:16:16Z mat $

PORTNAME=	netif
PORTVERSION=	1.0
PORTREVISION=	4
CATEGORIES=	net python
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}

MAINTAINER=	wg@FreeBSD.org
COMMENT=	Python network configuration library for FreeBSD

LICENSE=	BSD2CLAUSE

BUILD_DEPENDS=	cython>0:lang/cython

USE_GITHUB=     yes
GH_ACCOUNT=	freenas
GH_PROJECT=	py-netif
GH_TAGNAME=	722a2af

USES=		python
USE_PYTHON=	autoplist distutils

.include <bsd.port.pre.mk>

.if ${PYTHON_REL} < 3400
RUN_DEPENDS+=	${PYTHON_PKGNAMEPREFIX}enum34>0:devel/py-enum34
.endif

.include <bsd.port.post.mk>
