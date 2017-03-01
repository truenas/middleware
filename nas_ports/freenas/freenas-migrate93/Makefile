# $FreeBSD$

PORTNAME=	freenas-migrate93
PORTVERSION=	20170301
PORTREVISION=	1
CATEGORIES=	freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=	dev@ixsystems.com
COMMENT=	Tool to upgrade from 9.3 databases

RUN_DEPENDS=	python>0:${PORTSDIR}/lang/python \
		${PYTHON_PKGNAMEPREFIX}south>0:${PORTSDIR}/databases/py-south \
		${PYTHON_PKGNAMEPREFIX}bsd>0:${PORTSDIR}/freenas/py-bsd \
		${PYTHON_PKGNAMEPREFIX}lxml>0:${PORTSDIR}/devel/py-lxml

USES=		python
USE_GITHUB=	yes
GH_TUPLE+=	freenas:freenas-migrate93:aa6f6cb \
		freenas:django:d90c3a5:django

NO_BUILD=	yes
PRODUCT?=

.include <bsd.port.pre.mk>

do-install:
	${MKDIR} ${STAGEDIR}${PREFIX}/lib/migrate93
	cd ${WRKSRC} && ${COPYTREE_SHARE} src ${STAGEDIR}${PREFIX}/lib/migrate93/
	cd ${WRKSRC} && ${COPYTREE_SHARE} freenasUI ${STAGEDIR}${PREFIX}/lib/migrate93/
.if ${PRODUCT} == "TrueNAS"
	cd /usr/truenas/south_migrations && ${COPYTREE_SHARE} "." ${STAGEDIR}${PREFIX}/lib/migrate93/freenasUI/
.endif
	cd ${WRKSRC_django} && ${COPYTREE_SHARE} django ${STAGEDIR}${PREFIX}/lib/migrate93/
	${INSTALL_SCRIPT} ${WRKSRC}/sbin/migrate93 ${STAGEDIR}${PREFIX}/sbin/
	${PYTHON_CMD} -m compileall ${STAGEDIR}${PREFIX}/lib/migrate93
	(cd ${STAGEDIR}${PREFIX}/lib/migrate93; ${FIND} . -type f \
		| ${SED} -e 's,^\./,,g' \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn \
		| ${AWK} '{print "lib/migrate93/"$$2 }' >> ${TMPPLIST})

.include <bsd.port.post.mk>
