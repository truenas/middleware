# $FreeBSD$

PORTNAME=       freenas-docs
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=     freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        Userguide for UI
PRODUCT?=

BUILD_DEPENDS=	sphinx-build:${PORTSDIR}/textproc/py-sphinx \
		${PYTHON_PKGNAMEPREFIX}sphinxcontrib-httpdomain>0:${PORTSDIR}/textproc/py-sphinxcontrib-httpdomain \
		${PYTHON_PKGNAMEPREFIX}sphinx_numfig>r0:${PORTSDIR}/textproc/py-sphinx_numfig

USES=	perl5 python:build

EXTRACT_ONLY=
WRKSRC=		/usr/freenas_docs

.include <bsd.port.pre.mk>

.if ${PRODUCT} == "TrueNAS"
USES+=		gmake
BUILD_DEPENDS+=	gmake>0:${PORTSDIR}/devel/gmake \
		tex-formats>0:${PORTSDIR}/print/tex-formats \
		tex-dvipsk>0:${PORTSDIR}/print/tex-dvipsk
.endif


checksum fetch:
	echo ${.TARGET} not needed because building direct

do-build:
.if ${PRODUCT} == "TrueNAS"
	(cd ${WRKSRC}/userguide && make TAG="truenas" html \
		&& cd processed/_build/html && ${COPYTREE_SHARE} . ${WRKSRC}/userguide/processed_html \
		&& cd ${WRKSRC}/userguide && make TAG="truenas" pdf)
.else
	(cd ${WRKSRC}/userguide && make html)
.endif

do-install:
	${MKDIR} -p ${STAGEDIR}${PREFIX}/www/data/
.if ${PRODUCT} == "TrueNAS"
	${MV} ${WRKSRC}/userguide/processed_html ${STAGEDIR}${PREFIX}/www/data/docs
	${CP} -p ${WRKSRC}/userguide/processed/_build/latex/TrueNAS.pdf ${STAGEDIR}${PREFIX}/www/data/docs/
.else
	${MV} ${WRKSRC}/userguide/processed/_build/html ${STAGEDIR}${PREFIX}/www/data/docs
.endif
	(cd ${STAGEDIR}${PREFIX}/www/data/docs; ${FIND} . -type f \
		| ${SED} -e 's,^\./,,g' \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn \
		| ${AWK} '{print "www/data/docs/"$$2 }' >> ${TMPPLIST})

.include <bsd.port.post.mk>
