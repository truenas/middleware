# $FreeBSD$

PORTNAME=	freenas-sample
PORTVERSION=	0.02i
PORTREVISION=	0
CATEGORIES=	sysutils

USE_GITHUB=	yes
GH_ACCOUNT=	freenas
GH_PROJECT=	sample
GH_TAGNAME=	7d0c2b9

#USES=           python:2.7+
USES=		python:2.7+,build

BUILD_DEPENDS=	${LOCALBASE}/lib/libbfd.a:${PORTSDIR}/devel/libbfd
BUILD_DEPENDS+=	${LOCALBASE}/lib/libiberty.a:${PORTSDIR}/devel/gnulibiberty
BUILD_DEPENDS+=	${LOCALBASE}/lib/libxo.a:${PORTSDIR}/devel/libxo
BUILD_DEPENDS+=	${LOCALBASE}/bin/cython:${PORTSDIR}/lang/cython
BUILD_DEPENDS+=	${LOCALBASE}/bin/python:${PORTSDIR}/lang/python
MAKE_ENV=	SYSDIR=${SRC_BASE}/sys
#MAKE_ENV+=	DEBUG_FLAGS="-O0 -g"
#MAKE_ENV+=	KMODDIR=${STAGEDIR}/boot/kernel
#MAKE_ENV+=	BINDIR=${PREFIX}/bin


SSP_UNSAFE=	YES

.include <bsd.port.pre.mk>

checksum:
	true

.include <bsd.port.post.mk>
