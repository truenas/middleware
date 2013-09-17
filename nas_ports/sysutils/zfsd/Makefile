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

CATEGORIES=     sysutils

#VALID_CATEGORIES+= zfs
#CATEGORIES+=     zfs

MAINTAINER=     alfred@FreeBSD.org
COMMENT=        zfsd for TrueNAS

USE_XZ=		yes

# XXX: do we need this?  WE need it in nanobsd
#LOCALBASE?=/

# for testing
#LOCALBASE=/home/alfred/derp

# setting BINDIR doesn't work at this level.
#BINDIR=${LOCALBASE}/sbin
# LOCALBASE works better than PREFIX for some reason.
#PREFIX=/home/alfred/derp

# explicitly set this for the port build
FREEBSD_SRCTOP=/usr/src

GIT_REPO_URL=git@gitserver.ixsystems.com:/git/repos/truenas-build/git-repo/zfsd.git

#fetch:
#		echo not needed

#extract:
#		mkdir -p ${WRKDIR}
#		git clone /truenas-build/git-repo/zfsd.git ${WRKSRC}

#EXPORT_TAG=master
EXPORT_TAG=v${PORTVERSION}

git-export:
	git archive \
		--remote=${GIT_REPO_URL} \
		--prefix=${PORTNAME}-${PORTVERSION}/ \
		${EXPORT_TAG} | \
			xz > ${PORTNAME}-${PORTVERSION}.tar.xz

#/truenas-build/ports-distfiles/zfsd-${PORTVERSION}.tar.xz

# no checksum, we just used git!
checksum:
		echo no checksum needed

.include <bsd.port.mk>

