# Created by: kmoore@FreeBSD.org
# $FreeBSD$

PORTNAME=	grub2-freenas
PORTVERSION=	2.02p
PORTREVISION=	26
CATEGORIES=	sysutils
MASTER_SITES=   http://www.pcbsd.org/~kris/software/ \
		ftp://ftp.pcbsd.org/pub/software/
DISTNAME=	grub-2.02_5

MAINTAINER=	kmoore@FreeBSD.org
COMMENT=	Multiboot boot loader

LICENSE=	GPLv3

BUILD_DEPENDS=	${LOCALBASE}/bin/flex:${PORTSDIR}/textproc/flex \
		${LOCALBASE}/bin/bash:${PORTSDIR}/shells/bash \
		help2man:${PORTSDIR}/misc/help2man

WRKSRC=		${WRKDIR}/grub-2.02
CONFLICTS=	grub-0* grub2-2*
SSP_UNSAFE=	yes
USE_GCC=	yes
USE_AUTOTOOLS=	automake aclocal autoconf
ACLOCAL_ARGS=	-Im4
GNU_CONFIGURE=	yes
USES=		bison gettext gmake makeinfo python tar:xz
ONLY_FOR_ARCHS=	i386 amd64
INFO=		grub grub-dev
MAKE_JOBS_UNSAFE=	yes

CONFIGURE_ARGS=	--disable-werror --localedir=${PREFIX}/share/locale
CONFIGURE_ENV=	CPP="${CC} -E" \
		LEX=${LOCALBASE}/bin/flex

SUB_FILES=	00_header 10_kfreebsd 10_ktrueos 30_os-prober 50_otherbe

OPTIONS_DEFINE=	MKFONT FUSE
OPTIONS_DEFAULT=MKFONT
MKFONT_DESC=	Build grub-mkfont (require freetype2)
FUSE_DESC=	Build grub-mount (require FUSE)

.include <bsd.port.pre.mk>

.if ${ARCH} != "amd64"
EFIEMU=		"@comment "
.endif

PLIST_SUB+=	EFIEMU=${EFIEMU}

.if ${PORT_OPTIONS:MMKFONT}
LIB_DEPENDS+=	libfreetype.so:${PORTSDIR}/print/freetype2
BUILD_DEPENDS+=	${LOCALBASE}/share/fonts/dejavu/DejaVuSans.ttf:${PORTSDIR}/x11-fonts/dejavu \
		${LOCALBASE}/share/fonts/gnu-unifont/unifont.pcf.gz:${PORTSDIR}/x11-fonts/gnu-unifont
MAN1+=		grub-mkfont.1
CONFIGURE_ARGS+=	--enable-grub-mkfont
.else
CONFIGURE_ARGS+=	--disable-grub-mkfont
MKFONT=		"@comment "
.endif

PLIST_SUB+=	MKFONT=${MKFONT}

.if ${PORT_OPTIONS:MFUSE}
LIB_DEPENDS+=	libfuse.so:${PORTSDIR}/sysutils/fusefs-libs
CONFIGURE_ARGS+=	--enable-grub-mount
.else
CONFIGURE_ARGS+=	--disable-grub-mount
FUSE=		"@comment "
.endif

PLIST_SUB+=	FUSE=${FUSE}

post-patch:
	@${TOUCH} -t 200001010000 ${WRKSRC}/Makefile.util.def

pre-configure:
	@${REINPLACE_CMD} -e 's|python|${PYTHON_CMD}|g' ${WRKSRC}/autogen.sh
	cd ${WRKSRC} && ./autogen.sh

post-configure:
	@${LN} -sfh /usr/include/machine /usr/include/sys /usr/include/x86 ${WRKSRC}/grub-core

post-install:
	@${RM} -rf ${STAGEDIR}${PREFIX}/lib/charset.alias
	@${INSTALL_SCRIPT} ${WRKDIR}/00_header ${STAGEDIR}${PREFIX}/etc/grub.d/
	@${INSTALL_SCRIPT} ${WRKDIR}/10_kfreebsd ${STAGEDIR}${PREFIX}/etc/grub.d/
	@${INSTALL_SCRIPT} ${WRKDIR}/10_ktrueos ${STAGEDIR}${PREFIX}/etc/grub.d/
	@${INSTALL_SCRIPT} ${WRKDIR}/30_os-prober ${STAGEDIR}${PREFIX}/etc/grub.d/
	@${INSTALL_SCRIPT} ${WRKDIR}/50_otherbe ${STAGEDIR}${PREFIX}/etc/grub.d/
	@${MV} ${STAGEDIR}${PREFIX}/etc/grub.d/40_custom ${STAGEDIR}/${PREFIX}/etc/grub.d/40_custom.dist

.include <bsd.port.post.mk>

RUN_DEPENDS:=	${RUN_DEPENDS:Ngcc*}
