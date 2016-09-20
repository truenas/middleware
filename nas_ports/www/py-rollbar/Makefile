# $FreeBSD: head/devel/py-flake8/Makefile 415591 2016-05-21 11:53:36Z wg $

PORTNAME=	rollbar
PORTVERSION=	0.13.4
CATEGORIES=	www python
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}

MAINTAINER=	wg@FreeBSD.org
COMMENT=	Easy and powerful exception tracking with Rollbar

LICENSE=	MIT

RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}requests>0:www/py-requests \
		${PYTHON_PKGNAMEPREFIX}six>=1.5.7:devel/py-six

USES=		python
USE_PYTHON=	autoplist distutils
USE_GITHUB=	yes

GH_PROJECT=	pyrollbar
GH_TAGNAME=	v${PORTVERSION}

.include <bsd.port.mk>
