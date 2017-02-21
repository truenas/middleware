# Created by: Olivier Duchateau <duchateau.olivier@gmail.com>
# $FreeBSD: head/www/py-requests/Makefile 429495 2016-12-26 11:47:37Z antoine $

PORTNAME=	requests
PORTVERSION=	2.11.1
CATEGORIES=	www python
MASTER_SITES=	CHEESESHOP
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}

MAINTAINER=	koobs@FreeBSD.org
COMMENT=	HTTP library written in Python for human beings

LICENSE=	ISCL
LICENSE_FILE=	${WRKSRC}/LICENSE

TEST_DEPENDS=	${PYTHON_PKGNAMEPREFIX}pytest>=2.8.1:devel/py-pytest

USES?=		python
USE_PYTHON=	autoplist distutils

CONFLICTS_INSTALL=	py*-requests1-*

NO_ARCH=	yes

do-test:
	@cd ${WRKSRC} && ${PYTHON_CMD} ${PYDISTUTILS_SETUP} test

.include <bsd.port.mk>
