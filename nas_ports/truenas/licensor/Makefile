# New ports collection makefile for:    pstack
# Date created:         1 May 2002
# Whom:                 Peter Edwards <pmedwards@eircom.net>
#
# $FreeBSD: ports/sysutils/pstack/Makefile,v 1.10 2012/11/17 06:01:42 svnexp Exp $
# $Id: Makefile,v 1.2 2002/11/26 10:38:28 pmedwards Exp $
#

PORTNAME=       licensor
PORTVERSION=    ${PRODUCT_VERSION:C/\-.*//:C/\_.*//}
PORTREVISION=   ${REVISION}

CATEGORIES=     truenas

VALID_CATEGORIES+= truenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        licensor for TrueNAS

USE_XZ=		yes

# explicitly set this for the port build
FREEBSD_SRCTOP=/usr/src

EXTRACT_ONLY=
WRKSRC=/usr/nas_source/licensor

# no checksum, we just used git!
checksum fetch:
	echo ${.TARGET} not needed because building direct

MAKE_JOBS_UNSAFE=yes

do-build:
	${MAKE} -C ${WRKSRC}/build/client obj
	${MAKE} -C ${WRKSRC}/build/client all

do-install:
	${MKDIR} ${STAGEDIR}${PREFIX}/sbin
	${MAKE} -C ${WRKSRC}/build/client install BINDIR=${STAGEDIR}${PREFIX}/sbin
	cd ${STAGEDIR}${PREFIX}/sbin
	${SH} ${WRKSRC}/src/xzexe ix-licensor
	${RM} -f ${STAGEDIR}${PREFIX}/sbin/ix-licensor~


.include <bsd.port.mk>
