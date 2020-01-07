# $FreeBSD$

PORTNAME=	firmware
PORTVERSION=	201909261555
CATEGORIES=	freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=	dev@ixsystems.com
COMMENT=	Firmware files

USE_GITHUB=	yes
GH_TUPLE+=	freenas:firmware:86926bb

NO_BUILD=	yes

.include <bsd.port.pre.mk>

do-install:
	${MKDIR} ${STAGEDIR}${PREFIX}/lib/firmware
	cd ${WRKSRC} && ${COPYTREE_SHARE} . ${STAGEDIR}${PREFIX}/lib/firmware/
	(cd ${STAGEDIR}${PREFIX}/lib/firmware; ${FIND} . -type f \
		| ${SED} -e 's,^\./,,g' \
		| ${AWK} '{print length, $$0}' | ${SORT} -rn \
		| ${AWK} '{print "lib/firmware/"$$2 }' >> ${TMPPLIST})

.include <bsd.port.post.mk>
