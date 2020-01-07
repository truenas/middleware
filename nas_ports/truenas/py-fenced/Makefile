PORTNAME=	fenced
PORTVERSION=	0.1.2
PORTREVISION=	${REVISION}
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}

CATEGORIES=	truenas
VALID_CATEGORIES+=	truenas

MAINTAINER=	dev@ixsystems.com
COMMENT=	TrueNAS Fence Daemon

USES=		python
USE_PYTHON=	autoplist distutils
EXTRACT_ONLY=

BUILD_DEPENDS=	${PYTHON_PKGNAMEPREFIX}fastentrypoints>0:devel/py-fastentrypoints@${PY_FLAVOR}
RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}cam>0:devel/py-cam@${PY_FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}sysctl>0:devel/py-sysctl@${PY_FLAVOR}

WRKSRC=		/usr/nas_source/fenced

checksum fetch:
	echo ${.TARGET} not needed because building direct

.include <bsd.port.mk>
