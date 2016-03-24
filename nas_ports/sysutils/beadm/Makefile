# $FreeBSD$

PORTNAME=	beadm
PORTVERSION=	1.4
CATEGORIES=	sysutils

MAINTAINER=	kmoore@FreeBSD.org
COMMENT=	Solaris-like utility to manage Boot Environments on ZFS

LICENSE=	BSD2CLAUSE

USE_GITHUB=	yes
GH_ACCOUNT=	kmoore134
GH_COMMIT=	f100bec
GH_TAGNAME=	${GH_COMMIT}

NO_BUILD=	YES

CONFLICTS_INSTALL=	beadm-devel-*

PLIST_FILES=	sbin/${PORTNAME} \
		man/man1/${PORTNAME}.1.gz

do-install:
	${INSTALL_SCRIPT} ${WRKSRC}/${PORTNAME} \
	    ${STAGEDIR}${PREFIX}/sbin/${PORTNAME}
	${INSTALL_MAN} ${WRKSRC}/${PORTNAME}.1 \
	  ${STAGEDIR}${MANPREFIX}/man/man1/

.include <bsd.port.mk>
