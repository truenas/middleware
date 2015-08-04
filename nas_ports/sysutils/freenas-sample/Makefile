# $FreeBSD$

PORTNAME=	freenas-sample
PORTVERSION=	0.01a
PORTREVISION=	0
CATEGORIES=	sysutils

USE_GITHUB=	yes
GH_ACCOUNT=	freenas
GH_PROJECT=	sample
GH_TAGNAME=	5a631ab
MAKE_ENV=	SYSDIR=${SRC_BASE}/sys USE_BFD=NO
#MAKE_ENV+=	KMODDIR=${STAGEDIR}/boot/kernel
#MAKE_ENV+=	BINDIR=${PREFIX}/bin

SSP_UNSAFE=	YES

.include <bsd.port.pre.mk>

checksum:
	true

.include <bsd.port.post.mk>
