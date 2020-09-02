# $FreeBSD$

PORTNAME=	tc-stats	
PORTVERSION=	0.1.8
DISTVERSIONPREFIX=	v

CATEGORIES=	freenas
VALID_CATEGORIES+=	freenas

MAINTAINER=	dev@ixsystems.com
COMMENT=	TrueCommand Stats Collection Engine

NO_BUILD=	YES

USE_GITHUB=     yes
GH_ACCOUNT=     freenas
GH_PROJECT=     truecommand-stats

.include <bsd.port.pre.mk>

do-install:
	mkdir -p ${STAGEDIR}${PREFIX}/bin
	${INSTALL_PROGRAM} ${WRKSRC}/binaries/freebsd/trueview-stats ${STAGEDIR}${PREFIX}/bin/trueview_stats.sh

.include <bsd.port.post.mk>
