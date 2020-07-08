# $FreeBSD$

PORTNAME=	freenas-migrate113
PORTVERSION=	2020000000
PORTREVISION=	7
CATEGORIES=	freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=	dev@ixsystems.com
COMMENT=	Tool to upgrade to 11.3 database

RUN_DEPENDS=	python>0:${PORTSDIR}/lang/python

USES=		python
USE_GITHUB=	yes
GH_ACCOUNT=	freenas
GH_TAGNAME=	72778332bc0f5bf83a9db6039e82244d25f54580

NO_BUILD=	yes

.include <bsd.port.pre.mk>

do-install:
	${MKDIR} ${STAGEDIR}${PREFIX}/lib/migrate113
	cd ${WRKSRC} && ${COPYTREE_SHARE} django ${STAGEDIR}${PREFIX}/lib/migrate113/
	cd ${WRKSRC} && ${COPYTREE_SHARE} freenasUI ${STAGEDIR}${PREFIX}/lib/migrate113/
	cd ${WRKSRC} && ${COPYTREE_SHARE} src ${STAGEDIR}${PREFIX}/lib/migrate113/
	${INSTALL_SCRIPT} ${WRKSRC}/sbin/migrate113 ${STAGEDIR}${PREFIX}/sbin/
	${PYTHON_CMD} -m compileall ${STAGEDIR}${PREFIX}/lib/migrate113
	(cd ${STAGEDIR}${PREFIX}/lib/migrate113; ${FIND} . -type f \
		| ${SED} -e 's,^\./,,g' \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn \
		| ${AWK} '{print "lib/migrate113/"$$2 }' >> ${TMPPLIST})

.include <bsd.port.post.mk>
