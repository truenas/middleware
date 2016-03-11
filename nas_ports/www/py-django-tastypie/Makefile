# Created by: William Grzybowski <william88@gmail.com>
# $FreeBSD$

PORTNAME=	django-tastypie
PORTVERSION=	0.12.1
CATEGORIES=	www python
MASTER_SITES=	CHEESESHOP
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}

MAINTAINER=	wg@FreeBSD.org
COMMENT=	Create REST API for Django apps

LICENSE=	BSD3CLAUSE

MY_DEPENDS=	${PYTHON_PKGNAMEPREFIX}mimeparse>=0.1.4:${PORTSDIR}/devel/py-mimeparse \
		${PYTHON_PKGNAMEPREFIX}dateutil>=2.1:${PORTSDIR}/devel/py-dateutil

BUILD_DEPENDS=	${MY_DEPENDS}

RUN_DEPENDS?=	${MY_DEPENDS} \
		${PYTHON_PKGNAMEPREFIX}django16>=1.5:${PORTSDIR}/www/py-django16

USES=		python
USE_PYTHON=	distutils autoplist

CONFLICTS_INSTALL=	 ${PKGNAMEPREFIX}${PORTNAME}16

.include <bsd.port.mk>
