# Created by: Eduard Martinescu
# $FreeBSD: head/sysutils/smartmontools/Makefile 412136 2016-03-29 20:52:11Z amdmi3 $

PORTNAME=	smartmontools
PORTVERSION=	6.5
CATEGORIES=	sysutils
MASTER_SITES=	SF

MAINTAINER=	samm@os2.kiev.ua
COMMENT=	S.M.A.R.T. disk monitoring tools

LICENSE=	GPLv2+
LICENSE_FILE=	${WRKSRC}/COPYING

CONFLICTS=	smartmontools-devel-[0-9]*

OPTIONS_DEFINE=	DOCS

USES=		alias gmake shebangfix
SHEBANG_FILES=	examplescripts/Example5
GNU_CONFIGURE=	yes
CONFIGURE_ARGS=	--disable-dependency-tracking \
		--enable-sample \
		--with-initscriptdir=${PREFIX}/etc/rc.d

SUB_FILES=	pkg-message smart
USE_RC_SUBR=	smartd

PORTDOCS=	*

post-patch:
	@${REINPLACE_CMD} -e 's| install-initdDATA| |' ${WRKSRC}/Makefile.in

post-install:
	@${MKDIR} ${STAGEDIR}${PREFIX}/etc/periodic/daily
	${INSTALL_SCRIPT} ${WRKDIR}/smart \
		${STAGEDIR}${PREFIX}/etc/periodic/daily

.include <bsd.port.mk>
