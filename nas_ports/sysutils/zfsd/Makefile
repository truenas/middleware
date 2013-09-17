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


EXPORT_TAG=v${PORTVERSION}
GIT_REPO_URL=git@gitserver.ixsystems.com:/git/repos/truenas-build/git-repo/zfsd.git

#EXPORT_TAG=master

# Make a tarball from git for ourselves.
git-export:
	git archive \
		--remote=${GIT_REPO_URL} \
		--prefix=${PORTNAME}-${PORTVERSION}/ \
		${EXPORT_TAG} | \
			xz > ${PORTNAME}-${PORTVERSION}.tar.xz

#/truenas-build/ports-distfiles/zfsd-${PORTVERSION}.tar.xz

# if NAS_PORTS_DIRECT or NAS_PORTS_DIRECT_SYSUTILS_ZFSD is set
# then what we do is use the checked out copy of ZFSD.
.if defined(NAS_PORTS_DIRECT) ||defined(NAS_PORTS_DIRECT_SYSUTILS_ZFSD)

WRKSRC=/usr/ports/nas_source/zfsd
#WRKSRC=/home/alfred/tn/zfsd

# no checksum, we just used git!
checksum fetch extract:
	echo ${.TARGET} not needed because building direct

pre-clean:
	@cd ${WRKSRC} && ${MAKE} clean cleandepend

.endif

#
# Uncomment to test using git to pull sources instead of tarball
# EXTRACT_DEPENDS= ${LOCALBASE}/bin/git:${PORTSDIR}/devel/git
#extract:
#		mkdir -p ${WRKDIR}
#		git clone -b /truenas-build/git-repo/zfsd.git ${WRKSRC}


.include <bsd.port.mk>

