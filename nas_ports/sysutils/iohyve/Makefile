# $FreeBSD$

PORTNAME=	iohyve
PORTVERSION=	0.7.7
PORTREVISION=	2
CATEGORIES=	sysutils

MAINTAINER=	lme@FreeBSD.org
COMMENT=	bhyve manager utilizing ZFS and other FreeBSD tools

LICENSE=	BSD2CLAUSE
LICENSE_FILE=	${WRKSRC}/LICENSE

USE_GITHUB=	yes
GH_ACCOUNT=	pr1ntf

NO_BUILD=	yes
NO_ARCH=	yes

do-patch:
	${REINPLACE_CMD} 's%\$$(PREFIX)%${STAGEDIR}/$$(PREFIX)%g' ${WRKSRC}/Makefile
	${REINPLACE_CMD} 's%setup_freenas $$val%__setup_freenas $$val%g' ${WRKSRC}/lib/ioh-setup

.include <bsd.port.mk>
