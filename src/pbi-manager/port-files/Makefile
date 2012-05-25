# New ports collection makefile for:	pbi-manager
# Date created:				27 May 2010
# Whom:					Kris Moore <kmoore@FreeBSD.org>
#
# $FreeBSD$

PORTNAME=	pbi-manager
PORTVERSION=	0.9.8
CATEGORIES=	ports-mgmt
MASTER_SITES=	http://www.pcbsd.org/~kris/software/ \
		ftp://ftp.pcbsd.org/pub/software/

MAINTAINER=	kmoore@FreeBSD.org
COMMENT=	Push Button Installer Manager

RUN_DEPENDS=	xdg-desktop-icon:${PORTSDIR}/devel/xdg-utils

USE_BZIP2=	yes
NO_BUILD=	yes
SUB_FILES+=	pkg-message

MAN1=		pbi_add.1 pbi_browser.1 pbi_create.1 \
		pbi_delete.1 \
		pbi_icon.1 pbi_indextool.1 pbi_info.1 \
		pbi_listrepo.1 pbi_update.1 \
		pbi_metatool.1 \
		pbi_patch.1 \
		pbi_update_hashdir.1
MAN5=		pbi.conf.5
MAN8=		pbi_addrepo.8 pbi_autobuild.8 pbi_deleterepo.8 \
		pbi_makepatch.8 pbi_makeport.8 pbi_makerepo.8 pbid.8

do-install:
	cd ${WRKSRC} && ./install.sh ${LOCALBASE}

post-install:
	@${ECHO_MSG}
	@${CAT} ${PKGMESSAGE}
	@${ECHO_MSG}

.include <bsd.port.mk>
