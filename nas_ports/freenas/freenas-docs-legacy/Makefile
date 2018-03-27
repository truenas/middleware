# $FreeBSD$

PORTNAME=       freenas-docs-legacy
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=     freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        Userguide for legacy UI
PRODUCT?=

BUILD_DEPENDS=	sphinx-build:textproc/py-sphinx \
		${PYTHON_PKGNAMEPREFIX}sphinxcontrib-httpdomain>0:textproc/py-sphinxcontrib-httpdomain \
		${PYTHON_PKGNAMEPREFIX}sphinx_numfig>r0:textproc/py-sphinx_numfig

USES=	perl5 python:build

EXTRACT_ONLY=
WRKSRC=		/usr/freenas_docs_legacy

.include <bsd.port.pre.mk>

.if ${PRODUCT} == "TrueNAS"
USES+=		gmake
BUILD_DEPENDS+=	gmake>0:devel/gmake \
		tex-xetex>0:print/tex-xetex \
		tex-dvipdfmx>0:print/tex-dvipdfmx \
		tex-formats>0:print/tex-formats \
		tex-dvipsk>0:print/tex-dvipsk
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
	${MV} ${WRKSRC}/userguide/processed_html ${STAGEDIR}${PREFIX}/www/data/docs_legacy
	${CP} -p ${WRKSRC}/userguide/processed/_build/latex/TrueNAS.pdf ${STAGEDIR}${PREFIX}/www/data/docs_legacy/
.else
	${MV} ${WRKSRC}/userguide/processed/_build/html ${STAGEDIR}${PREFIX}/www/data/docs_legacy
.endif
	(cd ${STAGEDIR}${PREFIX}/www/data/docs_legacy; ${FIND} . -type f \
		| ${SED} -e 's,^\./,,g' \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn \
		| ${AWK} '{print "www/data/docs_legacy/"$$2 }' >> ${TMPPLIST})

.include <bsd.port.post.mk>
