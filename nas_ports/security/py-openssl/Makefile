# Created by: ijliao
# $FreeBSD: head/security/py-openssl/Makefile 422634 2016-09-22 16:15:32Z amdmi3 $

PORTNAME=	openssl
PORTVERSION=	16.2.0
CATEGORIES=	security python
MASTER_SITES=	CHEESESHOP
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}
DISTNAME=	pyOpenSSL-${PORTVERSION}

MAINTAINER=	sbz@FreeBSD.org
COMMENT=	Python interface to the OpenSSL library

LICENSE=	APACHE20
LICENSE_FILE=	${WRKSRC}/LICENSE

RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}cryptography>=0.2.1:security/py-cryptography \
		${PYTHON_PKGNAMEPREFIX}six>=1.5.2:devel/py-six

OPTIONS_DEFINE=	EXAMPLES

USES=		cpe python
USE_PYTHON=	autoplist concurrent distutils pythonprefix

CPE_VENDOR=	jean-paul_calderone
CPE_PRODUCT=	py${PORTNAME}

EXAMPLESDIR=	${PREFIX}/share/examples/py-${PORTNAME}
PORTEXAMPLES=	*

post-install:
	@${MKDIR} ${STAGEDIR}${EXAMPLESDIR}
	(cd ${WRKSRC}/examples/ && ${COPYTREE_SHARE} . ${STAGEDIR}${EXAMPLESDIR})

do-test:
	@(cd ${WRKSRC} && ${PYTHON_CMD} ${PYSETUP} test)

.include <bsd.port.mk>
