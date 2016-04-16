# $FreeBSD$

PORTNAME=	iohyve
PORTVERSION=	0.7.5
CATEGORIES=	sysutils

MAINTAINER=	lme@FreeBSD.org
COMMENT=	bhyve manager utilizing ZFS and other FreeBSD tools

LICENSE=	BSD2CLAUSE
LICENSE_FILE=	${WRKSRC}/LICENSE

USE_GITHUB=	yes
GH_ACCOUNT=	pr1ntf

NO_BUILD=	yes
NO_ARCH=	yes

PLIST_FILES=	etc/rc.d/iohyve man/man8/iohyve.8.gz sbin/iohyve

do-install:
	${INSTALL_SCRIPT} ${WRKSRC}/rc.d/iohyve ${STAGEDIR}${PREFIX}/etc/rc.d
	${INSTALL_SCRIPT} ${WRKSRC}/iohyve ${STAGEDIR}${PREFIX}/sbin
	${INSTALL_MAN} ${WRKSRC}/iohyve.8 ${STAGEDIR}${PREFIX}/man/man8

.include <bsd.port.mk>
