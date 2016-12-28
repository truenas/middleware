# $FreeBSD$

PORTNAME=	freenas-migrate93
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}
CATEGORIES=	freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=	dev@ixsystems.com
COMMENT=	Tool to upgrade from 9.3 databases

RUN_DEPENDS=	\
		${PYTHON_PKGNAMEPREFIX}django16>0:${PORTSDIR}/www/py-django16 \
		${PYTHON_PKGNAMEPREFIX}south>0:${PORTSDIR}/databases/py-south \
		${PYTHON_PKGNAMEPREFIX}bsd>0:${PORTSDIR}/freenas/py-bsd \
		${PYTHON_PKGNAMEPREFIX}lxml>0:${PORTSDIR}/devel/py-lxml

USES=		python
USE_PYTHON=	py3kplist
EXTRACT_ONLY=

NO_BUILD=	yes
MAKE_JOBS_UNSAFE= yes
WRKSRC=		/usr/migrate93_src

checksum fetch:
	${ECHO_CMD} ${.TARGET} not needed because building direct

do-install:
	${MKDIR} ${STAGEDIR}${PREFIX}/lib/migrate93
	cd ${WRKSRC} && ${COPYTREE_SHARE} src ${STAGEDIR}${PREFIX}/lib/migrate93/
	cd ${WRKSRC} && ${COPYTREE_SHARE} freenasUI ${STAGEDIR}${PREFIX}/lib/migrate93/
	${INSTALL_SCRIPT} ${WRKSRC}/sbin/migrate93 ${STAGEDIR}${PREFIX}/sbin/

post-install:
	${PYTHON_CMD} -m compileall ${STAGEDIR}${PREFIX}/lib/migrate93
	(cd ${STAGEDIR}${PREFIX}/lib/migrate93; ${FIND} . -type f \
		| ${SED} -e 's,^\./,,g' \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn \
		| ${AWK} '{print "lib/migrate93/"$$2 }' >> ${TMPPLIST})

.include <bsd.port.mk>
