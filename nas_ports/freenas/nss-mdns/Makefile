PORTNAME=	nss_mdns
PORTVERSION=	1.0
PORTREVISION=	${REVISION}

CATEGORIES=	freenas
VALID_CATEGORIES+=	freenas
MAINTAINER=	dev@ixsystems.com
COMMENT=	nsswitch module for mDNS support

BUILD_DEPENDS=	${LOCALBASE}/lib/libdns_sd.so:${PORTSDIR}/net/mDNSResponder
RUN_DEPENDS=	${LOCALBASE}/lib/libdns_sd.so:${PORTSDIR}/net/mDNSResponder

MAKE_ARGS+=	STAGEDIR="${STAGEDIR}"
MAKE_ARGS+=	MKDIR="${MKDIR}"
MAKE_ARGS+=	BSD_INSTALL_LIB="${BSD_INSTALL_LIB}"

NO_MTREE=
ALL_TARGRET=obj all

checksum fetch:
	echo ${.TARGET} not needed because building direct

extract:
	${MKDIR} ${WRKDIR}/${PORTNAME}-${PORTVERSION}

.include <bsd.port.mk>
