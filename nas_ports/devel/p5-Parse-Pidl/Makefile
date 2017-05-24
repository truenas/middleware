# $FreeBSD$

PORTNAME=		Parse-Pidl
PORTVERSION=		${SAMBA4_VERSION}
PORTREVISION=		0
PORTEPOCH=		0
CATEGORIES=		devel perl5
PKGNAMEPREFIX=		p5-
PKGNAMESUFFIX=

COMMENT=		IDL compiler written in Perl

LICENSE=		GPLv3

BUILD_DEPENDS=		p5-Parse-Yapp>=0:${PORTSDIR}/devel/p5-Parse-Yapp
RUN_DEPENDS:=		${BUILD_DEPENDS}

CONFLICTS=

SAMBA4_PORT?=		samba45
SAMBA4_SUBPORT=		yes

MASTERDIR=		${.CURDIR}/../../net/${SAMBA4_PORT}
PKGDIR=			${.CURDIR}

USES=			perl5
USE_PERL5=		configure
PATCH_WRKSRC=		${WRKDIR}/${DISTNAME}

post-extract:
			@${RM} -rf ${WRKSRC}/lib/Parse/Yapp ${WRKSRC}/lib/wscript_build

.include "${MASTERDIR}/Makefile"

# Ugly hack
WRKSRC=			/usr/samba_src/pidl
