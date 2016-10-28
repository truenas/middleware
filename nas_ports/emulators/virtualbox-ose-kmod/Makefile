# Created by: Bernhard Froehlich <decke@bluelife.at>
# $FreeBSD$

PORTNAME=	virtualbox-ose
PORTVERSION=	5.1.6
CATEGORIES=	emulators
MASTER_SITES=	http://download.virtualbox.org/virtualbox/${PORTVERSION}/
PKGNAMESUFFIX=	-kmod
DISTNAME=	VirtualBox-${PORTVERSION}

MAINTAINER=	vbox@FreeBSD.org
COMMENT=	VirtualBox kernel module for FreeBSD

LICENSE=	GPLv2
LICENSE_FILE=	${WRKSRC}/COPYING

BUILD_DEPENDS=	kmk:devel/kBuild

CPE_VENDOR=	oracle
CPE_PRODUCT=	vm_virtualbox

USES=		cpe kmod tar:bzip2
PATCHDIR=	${.CURDIR}/../${PORTNAME}/files
WRKSRC=		${WRKDIR}/VirtualBox-${PORTVERSION}
USE_RC_SUBR=	vboxnet
ONLY_FOR_ARCHS=	i386 amd64

HAS_CONFIGURE=	yes
CONFIGURE_ARGS+=	--build-headless
CONFIGURE_ARGS+=	--disable-alsa \
			--disable-dbus \
			--disable-docs \
			--disable-libvpx \
			--disable-pulse \
			--disable-python \
			--disable-sdl-ttf \
			--disable-xpcom
CONFIGURE_ARGS+=	--nofatal --with-gcc="${CC}" --with-g++="${CXX}"

CONFLICTS_INSTALL=	virtualbox-ose-kmod-devel-4* \
			virtualbox-ose-kmod-legacy-4*

OPTIONS_DEFINE=	DEBUG VIMAGE
OPTIONS_SUB=	yes
DEBUG_DESC=	Debug symbols, additional logs and assertions
VIMAGE_DESC=	VIMAGE virtual networking support

.include <bsd.port.options.mk>

VBOX_BIN=	${WRKSRC}/out/${KMK_ARCH}/${KMK_BUILDTYPE}/bin/src
VBOX_KMODS=	vboxdrv \
		vboxnetadp \
		vboxnetflt

BUILD_WRKSRC=	${VBOX_BIN}

KMK_BUILDTYPE=	release
KMK_CONFIG=	VBOX_LIBPATH_X11=${LOCALBASE} VBOX_FREEBSD_SRC=${SRC_BASE}/sys
KMK_FLAGS=	HostDrivers-scripts vboxdrv-mod VBoxNetFlt-src VBoxNetAdp-src

.if ${PORT_OPTIONS:MDEBUG}
KMK_FLAGS+=	BUILD_TYPE=debug
KMK_BUILDTYPE=	debug
EXTRA_PATCHES+=	${PATCHDIR}/extrapatch-Config.kmk \
		${PATCHDIR}/extrapatch-src-VBox-HostDrivers-Support-freebsd-Makefile
MAKE_ARGS+=	DEBUG_FLAGS="-O1 -g"
.endif

.if ${ARCH} == i386
KMK_ARCH=	freebsd.x86
.else
KMK_ARCH=	freebsd.${ARCH}
.endif

.include <bsd.port.pre.mk>

post-patch:
	@${ECHO} 'VBOX_WITH_VBOXDRV = 1' > ${WRKSRC}/LocalConfig.kmk
	@${ECHO} 'VBOX_WITH_NETFLT = 1' >> ${WRKSRC}/LocalConfig.kmk
	@${ECHO} 'VBOX_WITH_NETADP = 1' >> ${WRKSRC}/LocalConfig.kmk
	@${ECHO} 'VBOX_WITH_ADDITIONS =' >> ${WRKSRC}/LocalConfig.kmk
.if ${PORT_OPTIONS:MVIMAGE}
	@${ECHO} 'VBOX_WITH_NETFLT_VIMAGE = 1' >> ${WRKSRC}/LocalConfig.kmk
.endif
	@${REINPLACE_CMD} -e 's|/usr/local|${LOCALBASE}|g' \
	    ${WRKSRC}/Config.kmk ${WRKSRC}/configure
	@${REINPLACE_CMD} \
	    -e 's|\$$KBUILDDIR_BIN/kmk_sed|${LOCALBASE}/bin/kmk_sed|g' \
	    ${WRKSRC}/configure

pre-build:
	cd ${WRKSRC}/src/VBox/HostDrivers && ${SH} -c \
	    '. ${WRKSRC}/env.sh && ${KMK_CONFIG} ${LOCALBASE}/bin/kmk ${KMK_FLAGS}'

do-install:
	${MKDIR} ${STAGEDIR}${KMODDIR}
.for i in ${VBOX_KMODS}
	${INSTALL_KLD} ${VBOX_BIN}/${i}/${i}.ko ${STAGEDIR}${KMODDIR}
.if ${PORT_OPTIONS:MDEBUG}
	${INSTALL_KLD} ${VBOX_BIN}/${i}/${i}.ko.symbols ${STAGEDIR}${KMODDIR}
.endif
.endfor

.include <bsd.port.post.mk>
