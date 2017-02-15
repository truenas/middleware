# $FreeBSD$

PORTNAME=	py-consul
PORTVERSION=	0.7.0
DISTVERSIONPREFIX=	v
CATEGORIES=	sysutils

MAINTAINER=	jhixson@gmail.com
COMMENT=	Python client for consul

LICENSE=	MIT

BUILD_DEPENDS=	${PYTHON_PKGNAMEPREFIX}requests>=2.0.0:www/py3-requests \
				${PYTHON_PKGNAMEPREFIX}six>=1.4:devel/py3-six
RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}requests>=2.0.0:www/py3-requests \
				${PYTHON_PKGNAMEPREFIX}six>=1.4:devel/py3-six

USE_GITHUB=	yes
GH_ACCOUNT=	cablehead
GH_PROJECT=	python-consul

USES=	python:3.3+
USE_PYTHON=	distutils autoplist

.include <bsd.port.mk>
