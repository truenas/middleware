# Created by: mbr@FreeBSD.org
# $FreeBSD$

PORTNAME=		open-vm-tools
PORTVERSION=		${BUILD_VER}
PORTREVISION=		15
PORTEPOCH=		1
CATEGORIES=		emulators
MASTER_SITES=		SF/${PORTNAME}/${PORTNAME}/stable-9.4.x
DISTNAME=		open-vm-tools-${RELEASE_VER}-${BUILD_VER}

MAINTAINER=		swills@FreeBSD.org
COMMENT?=		Open VMware tools for FreeBSD VMware guests

LICENSE=		LGPL21
LICENSE_FILE=		${WRKSRC}/COPYING

RELEASE_VER=		9.4.0
BUILD_VER=		1280544

OPTIONS_DEFINE=		X11 LIBNOTIFY UNITY FUSE DNET ICU
OPTIONS_DEFAULT=	X11 LIBNOTIFY FUSE DNET ICU
OPTIONS_SUB=

DNET_DESC=		libdnet support
LIBNOTIFY_DESC=		Desktop notification support
UNITY_DESC=		liburiparser support

X11_CONFIGURE_WITH=	x gtk2 gtkmm
X11_LDFLAGS=		-L${LOCALBASE}/lib
X11_USE=		xorg=x11,ice,sm,xext,xineramaproto,xinerama,xrandr,xrender,xtst \
			gnome=gtk20,gtkmm24
X11_USES=		fuse
LIBNOTIFY_LIB_DEPENDS=	libnotify.so:devel/libnotify
UNITY_CONFIGURE_ENV=	CUSTOM_URIPARSER_CPPFLAGS="-I${LOCALBASE}/include/uriparser"
UNITY_LIB_DEPENDS=	liburiparser.so:net/uriparser
UNITY_CONFIGURE_ENABLE=	unity
DNET_CONFIGURE_WITH=	dnet
DNET_LIB_DEPENDS=	libdnet.so:net/libdnet
ICU_CONFIGURE_WITH=	icu
ICU_LIB_DEPENDS=	libicuuc.so:devel/icu

WRKSRC=			${WRKDIR}/open-vm-tools-${RELEASE_VER}-${BUILD_VER}
GNU_CONFIGURE=		yes
USES=			pkgconfig kmod libtool
USE_GNOME=		glib20
USE_LDCONFIG=		yes
CPPFLAGS+=		-Wno-deprecated-declarations

SSP_UNSAFE=		kernel module does not support ssp

CONFIGURE_ARGS+=	--without-procps --sysconfdir=${LOCALBASE}/etc

CONFLICTS+=		vmware-guestd[0-9]* vmware-tools[0-9]*
SUB_FILES=		pkg-message

USE_RC_SUBR=		vmware-guestd vmware-kmod

.include <bsd.port.options.mk>

.if ${PORT_OPTIONS:MX11}
CONFLICTS=		open-vm-tools-nox11-[0-9]*
.else
CONFLICTS=		open-vm-tools-[0-9]*
.endif

.include <bsd.port.pre.mk>

.if ${ARCH} == "sparc64"
IGNORE=		not yet ported to sparc64
.endif

post-build:
	cd ${WRKSRC}/modules && ${SETENV} ${MAKE_ENV} ${MAKE} ${MAKE_ARGS}

post-install:
	${MKDIR} ${STAGEDIR}${PREFIX}/lib/vmware-tools/modules/drivers
	${MKDIR} ${STAGEDIR}${PREFIX}/lib/vmware-tools/modules/input
	${INSTALL_DATA} ${WRKSRC}/modules/freebsd/vmmemctl.ko ${STAGEDIR}${PREFIX}/lib/vmware-tools/modules/drivers/vmmemctl.ko
	${INSTALL_DATA} ${WRKSRC}/modules/freebsd/vmxnet.ko ${STAGEDIR}${PREFIX}/lib/vmware-tools/modules/drivers/vmxnet.ko
	${INSTALL_DATA} ${WRKSRC}/modules/freebsd/vmhgfs.ko ${STAGEDIR}${PREFIX}/lib/vmware-tools/modules/drivers/vmhgfs.ko
	${INSTALL_DATA} ${WRKSRC}/modules/freebsd/vmblock.ko ${STAGEDIR}${PREFIX}/lib/vmware-tools/modules/drivers/vmblock.ko
	${MKDIR} ${STAGEDIR}${PREFIX}/share/open-vm-tools/scripts/vmware/
	${MKDIR} ${STAGEDIR}${PREFIX}/share/open-vm-tools/scripts/
	${MKDIR} ${STAGEDIR}${PREFIX}/share/open-vm-tools/tests/

.include <bsd.port.post.mk>
