# $FreeBSD$

PORTNAME=	tw_cli
PORTVERSION=	9.5.5
PORTREVISION=	1
CATEGORIES=	sysutils
MASTER_SITES=	http://www.avagotech.com/docs-and-downloads/raid-controllers/raid-controllers-common-files/
DISTNAME=	CLI_freebsd-from_the_10-2-2-1_9-5-5-1_codesets
DIST_SUBDIR=	3dm2

MAINTAINER=	jpaetzel@FreeBSD.org
COMMENT=	3ware storage controllers management CLI

LICENSE=	tw_cli
LICENSE_NAME=	LSI
LICENSE_TEXT=	${RESTRICTED}
LICENSE_PERMS=	no-dist-mirror no-dist-sell no-pkg-mirror no-pkg-sell auto-accept

RESTRICTED=	Source recipient must acknowledge license. Reproduction or redistribution prohibited. See http://www.lsi.com/Pages/user/eula.aspx

USES=		zip

# i386 binary should work on ia64, but not tested
ONLY_FOR_ARCHS=	i386 amd64 ia64
NO_BUILD=	yes
NO_WRKSUBDIR=	yes

SUB_FILES=	407.status-3ware-raid
PORTDOCS=	tw_cli.8.html
PLIST_FILES=	etc/periodic/daily/407.status-3ware-raid\
		man/man8/tw_cli.8.gz sbin/tw_cli

do-install:
	${INSTALL_PROGRAM} ${WRKSRC}/${ARCH:S,i386,x86,:S,amd64,x86_64,:S,ia64,x86,}/tw_cli\
		${STAGEDIR}${PREFIX}/sbin/tw_cli
	${INSTALL_MAN} ${WRKSRC}/tw_cli.8.nroff\
		${STAGEDIR}${MAN8PREFIX}/man/man8/tw_cli.8
	@${MKDIR} ${STAGEDIR}${PREFIX}/etc/periodic/daily
	${INSTALL_SCRIPT} ${WRKDIR}/407.status-3ware-raid \
		${STAGEDIR}${PREFIX}/etc/periodic/daily/
	@${MKDIR} ${STAGEDIR}${DOCSDIR}
	${INSTALL_DATA} ${WRKSRC}/${PORTDOCS} ${STAGEDIR}${DOCSDIR}

.include <bsd.port.mk>
