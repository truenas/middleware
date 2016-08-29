# Created by: Alexander Motin <mav@FreeBSD.org>
# $FreeBSD$

PORTNAME=	sedutil
PORTVERSION=	1.12
CATEGORIES=	sysutils

MAINTAINER=	mav@FreeBSD.org
COMMENT=	Self Encrypting Drive Utility

LICENSE=	GPLv3

USES=		gmake
USE_GITHUB=	yes
GH_ACCOUNT=	amotin
GH_TAGNAME=	d0eafad

PLIST_FILES=	sbin/sedutil-cli

do-build:
	(cd ${WRKSRC}/freebsd/CLI/ && gmake)

do-install:
	${INSTALL_PROGRAM} ${WRKSRC}/freebsd/CLI/dist/Release/CLang-Generic/sedutil-cli ${STAGEDIR}${PREFIX}/sbin

.include <bsd.port.mk>
