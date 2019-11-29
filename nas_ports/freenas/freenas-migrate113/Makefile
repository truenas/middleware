# $FreeBSD$

PORTNAME=	freenas-migrate113
PORTVERSION=	20191129
CATEGORIES=	freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=	dev@ixsystems.com
COMMENT=	Tool to upgrade to 11.3 database

RUN_DEPENDS=	python>0:${PORTSDIR}/lang/python

USES=		python
USE_GITHUB=	yes
GH_TUPLE+=	freenas:freenas-migrate113:a109b3e256637481d188632498ae21308931017e

NO_BUILD=	yes

.include <bsd.port.pre.mk>

do-install:
	${MKDIR} ${STAGEDIR}${PREFIX}/lib/migrate113
	cd ${WRKSRC} && ${COPYTREE_SHARE} freenasUI ${STAGEDIR}${PREFIX}/lib/migrate113/
	cd ${WRKSRC} && ${COPYTREE_SHARE} src ${STAGEDIR}${PREFIX}/lib/migrate113/
	${INSTALL_SCRIPT} ${WRKSRC}/sbin/migrate113 ${STAGEDIR}${PREFIX}/sbin/
	${PYTHON_CMD} -m compileall ${STAGEDIR}${PREFIX}/lib/migrate113
	(cd ${STAGEDIR}${PREFIX}/lib/migrate113; ${FIND} . -type f \
		| ${SED} -e 's,^\./,,g' \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn \
		| ${AWK} '{print "lib/migrate113/"$$2 }' >> ${TMPPLIST})

.include <bsd.port.post.mk>
