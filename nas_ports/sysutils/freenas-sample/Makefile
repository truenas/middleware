# $FreeBSD$

PORTNAME=	freenas-sample
PORTVERSION=	0.01c
PORTREVISION=	0
CATEGORIES=	sysutils

USE_GITHUB=	yes
GH_ACCOUNT=	freenas
GH_PROJECT=	sample
GH_TAGNAME=	4fb87bf

BUILD_DEPENDS=	${LOCALBASE}/lib/libbfd.a:${PORTSDIR}/devel/libbfd
BUILD_DEPENDS+=	${LOCALBASE}/lib/libiberty.a:${PORTSDIR}/devel/gnulibiberty
BUILD_DEPENDS+=	${LOCALBASE}/lib/libxo.a:${PORTSDIR}/devel/libxo
MAKE_ENV=	SYSDIR=${SRC_BASE}/sys
#MAKE_ENV+=	KMODDIR=${STAGEDIR}/boot/kernel
#MAKE_ENV+=	BINDIR=${PREFIX}/bin

SSP_UNSAFE=	YES

.include <bsd.port.pre.mk>

checksum:
	true

.include <bsd.port.post.mk>
