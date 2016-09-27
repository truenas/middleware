# $FreeBSD: head/net/py-s3transfer/Makefile 422159 2016-09-14 19:47:43Z pawel $

PORTNAME=	s3transfer
PORTVERSION=	0.1.4
CATEGORIES=	net python
MASTER_SITES=	CHEESESHOP
PKGNAMEPREFIX=	${PYTHON_PKGNAMEPREFIX}

MAINTAINER=	bradleythughes@fastmail.fm
COMMENT=	Amazon S3 Transfer Manager for Python

LICENSE=	APACHE20
LICENSE_FILE=	${WRKSRC}/LICENSE.txt

RUN_DEPENDS=	${PYTHON_PKGNAMEPREFIX}botocore>=1.3.0:devel/py-botocore
TEST_DEPENDS=	${PYTHON_PKGNAMEPREFIX}nose>=1.3.3:devel/py-nose \
		${PYTHON_PKGNAMEPREFIX}mock>=1.3.0:devel/py-mock

#Actually -2.7,3.3-3.5
USES=		python
USE_PYTHON=	autoplist distutils

NO_ARCH=	yes

.include <bsd.port.pre.mk>

.if ${PYTHON_REL} < 3000
RUN_DEPENDS+=	${PYTHON_PKGNAMEPREFIX}futures>=2.2.0:devel/py-futures
.endif

# setup.py test runs integration tests which fail
# https://github.com/boto/s3transfer/issues/41
do-test:
	@cd ${WRKSRC} && ${PYTHON_CMD} -m nose -v tests/unit tests/functional

.include <bsd.port.post.mk>
