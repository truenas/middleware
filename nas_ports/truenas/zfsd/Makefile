# New ports collection makefile for:    pstack
# Date created:         1 May 2002
# Whom:                 Peter Edwards <pmedwards@eircom.net>
#
# $FreeBSD: ports/sysutils/pstack/Makefile,v 1.10 2012/11/17 06:01:42 svnexp Exp $
# $Id: Makefile,v 1.2 2002/11/26 10:38:28 pmedwards Exp $
#

PORTNAME=       zfsd
PORTVERSION=    1.0
#PORTREVISION=   1

CATEGORIES=     truenas

VALID_CATEGORIES+= truenas

MAINTAINER=     dev@ixsystems.com
COMMENT=        zfsd for TrueNAS

USES+=		uidfix

# explicitly set this for the port build
FREEBSD_SRCTOP=/usr/src

EXTRACT_ONLY=
WRKSRC?=/usr/nas_source/zfsd

# no checksum, we just used git!
 #extract:
checksum fetch:
	echo ${.TARGET} not needed because building direct

pre-clean:
	@cd ${WRKSRC} && ${MAKE} clean cleandepend

pre-install:
	@${MKDIR} ${STAGEDIR}/etc/rc.d

ALL_TARGET=obj all

.include <bsd.port.mk>
