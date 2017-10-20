# $FreeBSD$

PORTNAME=	swagger-ui
PORTVERSION=	3.3.2

CATEGORIES=		freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=	dev@ixsystems.com
COMMENT=	OpenAPI spec renderer UI

EXTRACT_ONLY=

FETCH_DEPENDS=	npm>0:www/npm

NO_BUILD=	yes

checksum:
	${ECHO_CMD} ${.TARGET} not needed because building direct

fetch:
	${MKDIR} ${WRKSRC}
	(cd ${WRKSRC} && ${LOCALBASE}/bin/npm install swagger-ui-dist@${PORTVERSION})

extract:
	:

do-install:
	mkdir -p ${STAGEDIR}${PREFIX}/www/swagger-ui/
	(cd ${WRKSRC} && cp -r * ${STAGEDIR}${PREFIX}/www/swagger-ui/)
	(cd ${STAGEDIR}${PREFIX}/www/swagger-ui; ${FIND} . -type f \
		| ${SED} -e 's,^\./,,g' \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn \
		| cut -d " " -f 2- \
		| ${AWK} '{print "www/swagger-ui/"$$0 }' >> ${TMPPLIST})

.include <bsd.port.mk>
