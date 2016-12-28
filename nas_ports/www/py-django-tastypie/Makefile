# Created by: William Grzybowski <william88@gmail.com>
# $FreeBSD: head/www/py-django-tastypie/Makefile 424452 2016-10-22 08:21:52Z koobs $

PORTNAME=	django-tastypie
PORTVERSION=	0.13.3
PORTREVISION=	1
CATEGORIES=	www python
MASTER_SITES=	CHEESESHOP
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}

MAINTAINER?=	wg@FreeBSD.org
COMMENT=	Create REST API for Django apps

LICENSE=	BSD3CLAUSE

MY_DEPENDS=	${PYTHON_PKGNAMEPREFIX}mimeparse>=0.1.4:devel/py-mimeparse \
		${PYTHON_PKGNAMEPREFIX}dateutil>=2.1:devel/py-dateutil

BUILD_DEPENDS=	${MY_DEPENDS}

RUN_DEPENDS?=	${MY_DEPENDS} \
		${PYTHON_PKGNAMEPREFIX}django110>0:www/py-django110

USES=		python
USE_PYTHON=	distutils autoplist

CONFLICTS_INSTALL=	 ${PKGNAMEPREFIX}${PORTNAME}16

.include <bsd.port.mk>
