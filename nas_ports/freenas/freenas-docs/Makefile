# $FreeBSD$

PORTNAME=       freenas-docs
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=     freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        Userguide for UI

BUILD_DEPENDS=	sphinx-build:${PORTSDIR}/textproc/py-sphinx \
		${PYTHON_PKGNAMEPREFIX}sphinxcontrib-httpdomain>0:${PORTSDIR}/textproc/py-sphinxcontrib-httpdomain

USES=	python:build

EXTRACT_ONLY=
WRKSRC=		/usr/freenas_docs

checksum fetch:
	echo ${.TARGET} not needed because building direct

.include <bsd.port.pre.mk>

do-build:
.if ${PRODUCT} == "TrueNAS"
	(cd ${WRKSRC}/userguide && make SPHINXOPTS="-t truenas" html)
.else
	(cd ${WRKSRC}/userguide && make html)
.endif

do-install:
	${MKDIR} -p ${STAGEDIR}${PREFIX}/www/data/
	${MV} ${WRKSRC}/userguide/_build/html ${STAGEDIR}${PREFIX}/www/data/docs
	(cd ${STAGEDIR}${PREFIX}/www/data/docs; ${FIND} . -type f \
		| ${SED} -e 's,^\./,,g' \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn \
		| ${AWK} '{print "www/data/docs/"$$2 }' >> ${TMPPLIST})

.include <bsd.port.post.mk>
