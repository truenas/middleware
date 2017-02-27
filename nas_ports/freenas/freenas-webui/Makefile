# $FreeBSD$

PORTNAME=	freenas-webui
PORTVERSION=	${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=	${REVISION}

CATEGORIES=		freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=	dev@ixsystems.com
COMMENT=	Angular 2 Web User Interface for FreeNAS

EXTRACT_ONLY=

FETCH_DEPENDS=	npm2>0:${PORTSDIR}/www/npm2 \
		git>0:${PORTSDIR}/devel/git
RUN_DEPENDS=	npm2>0:${PORTSDIR}/www/npm2
BUILD_DEPENDS=	rsync>0:${PORTSDIR}/net/rsync

NO_BUILD=	yes
WRKSRC=		/usr/nas_source/webui

checksum:
	${ECHO_CMD} ${.TARGET} not needed because building direct

fetch:
	${MKDIR} ${WRKDIR}
	(cd ${WRKSRC} && ${LOCALBASE}/bin/npm install && ${LOCALBASE}/bin/npm build:prod)

extract:
	:

do-install:
	mkdir -p ${STAGEDIR}${PREFIX}/www/webui/
	rsync -avl --exclude '.git' --exclude 'nas_ports' --exclude 'etc' --exclude 'sbin' ${WRKSRC}/dist/ ${STAGEDIR}${PREFIX}/www/webui/
	(cd ${STAGEDIR}${PREFIX}/www/webui; ${FIND} . -type f \
		| ${SED} -e 's,^\./,,g' \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn \
		| cut -d " " -f 2- \
		| ${AWK} '{print "www/webui/"$$0 }' >> ${TMPPLIST})

.include <bsd.port.mk>
