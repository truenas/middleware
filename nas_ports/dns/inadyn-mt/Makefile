# Created by: William Grzybowski <william88@gmail.com>
# $FreeBSD$

PORTNAME=	inadyn-mt
PORTVERSION=	02.28.07
CATEGORIES=	dns
MASTER_SITES=	SF/${PORTNAME}/${PORTNAME}/${PORTNAME}.v.${PORTVERSION}/
DISTNAME=	${PORTNAME}.v.${PORTVERSION}

MAINTAINER=	wg@FreeBSD.org
COMMENT=	Simple dynamic dns client

LICENSE=	GPLv3

USES=		autoreconf
USE_RC_SUBR=	inadyn-mt
GNU_CONFIGURE=	yes

CONFIGURE_ARGS=	--disable-sound
MAKE_ARGS+=	INSTALL_PREFIX="${STAGEDIR}${PREFIX}/etc"

PORTDOCS=	readme.html AUTHORS README
PORTEXAMPLES=	*

PLIST_FILES=	bin/inadyn-mt etc/inadyn-mt/lang/en.lng \
		man/man5/inadyn-mt.conf.5.gz \
		man/man8/inadyn-mt.8.gz

OPTIONS_DEFINE=	DOCS EXAMPLES

.include <bsd.port.options.mk>

post-patch:
	@${REINPLACE_CMD} -e "s,%%PREFIX%%,${PREFIX},g" \
		${WRKSRC}/man/inadyn-mt.8 ${WRKSRC}/readme.html \
		${WRKSRC}/src/dyndns.h

pre-configure:
	@${REINPLACE_CMD} -e "s,INSTALL_PREFIX=.*,,g" ${WRKSRC}/configure.ac

post-install:
.if ${PORT_OPTIONS:MDOCS}
	@${MKDIR} ${STAGEDIR}${DOCSDIR}
	${INSTALL_DATA} ${PORTDOCS:S,^,${WRKSRC}/,} ${STAGEDIR}${DOCSDIR}
.endif
.if ${PORT_OPTIONS:MEXAMPLES}
	@${MKDIR} ${STAGEDIR}${EXAMPLESDIR}
	${INSTALL_DATA} ${WRKSRC}/inadyn-mt.conf ${STAGEDIR}${EXAMPLESDIR}
.endif

.include <bsd.port.mk>
