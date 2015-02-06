# $FreeBSD$

PORTNAME=	keyserverlib
PORTVERSION=	1.0
CATEGORIES=	truenas
VALID_CATEGORIES+=	truenas
MASTER_SITES=	CHEESESHOP
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}

MAINTAINER=	wg@FreeBSD.org
COMMENT=	Code checking using pep8 and pyflakes

LICENSE=	MIT

FETCH_DEPENDS=	git:${PORTSDIR}/devel/git
RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}enum34>=:${PORTSDIR}/devel/py-enum34

USES=		python
USE_PYTHON=	autoplist distutils

EXTRACT_ONLY=
WRKSRC?=/usr/nas_source/keyserver/keyserverlib

# no checksum, we just used git!
 #extract:
checksum fetch:
	echo ${.TARGET} not needed because building direct


.include <bsd.port.mk>
