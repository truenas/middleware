# $FreeBSD: head/textproc/py-ucl/Makefile 423300 2016-10-04 20:05:14Z wg $

PORTNAME=	ucl
PORTVERSION=	0.8.0
CATEGORIES=	textproc python
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}

MAINTAINER=	wg@FreeBSD.org
COMMENT=	UCL parser and emmitter

LICENSE=	MIT
LICENSE_FILE=	${WRKDIR}/libucl-${PORTVERSION}/COPYING

LIB_DEPENDS=	libucl.so:textproc/libucl

USES=		python
USE_GITHUB=	yes
USE_PYTHON=	autoplist concurrent distutils

GH_ACCOUNT=	vstakhov
GH_PROJECT=	libucl

WRKSRC=		${WRKDIR}/libucl-${PORTVERSION}/python

.include <bsd.port.mk>
