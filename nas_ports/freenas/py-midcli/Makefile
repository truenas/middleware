PORTNAME=	midcli
PORTVERSION=	20190509171453
PKGNAMEPREFIX=  ${PYTHON_PKGNAMEPREFIX}

CATEGORIES=     freenas
VALID_CATEGORIES+= freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        FreeNAS Middleware Command Line Interface

USES=		python
USE_PYTHON=	autoplist distutils

BUILD_DEPENDS=	${PYTHON_PKGNAMEPREFIX}fastentrypoints>0:devel/py-fastentrypoints@${FLAVOR}
RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}middlewared>0:freenas/py-middlewared@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}ply>0:devel/py-ply@${FLAVOR} \
		${PYTHON_PKGNAMEPREFIX}prompt_toolkit>0:devel/py-prompt_toolkit@${FLAVOR}

USE_GITHUB=	yes
GH_ACCOUNT=	freenas
GH_PROJECT=	midcli
GH_TAGNAME=	5ac8045e9f1f4a6cee30fbc698df8cb01f6e9d75

.include <bsd.port.mk>
