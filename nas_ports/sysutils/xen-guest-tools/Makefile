# Created by: Evan Sarmiento <esarmiento@wayfair.com>
# $FreeBSD$

PORTNAME=	xen-guest-tools
PORTVERSION=	4.7.1
CATEGORIES=	sysutils
MASTER_SITES=	http://bits.xensource.com/oss-xen/release/${PORTVERSION}/
DISTNAME=	xen-${PORTVERSION}

MAINTAINER=	dinoex@FreeBSD.org
COMMENT=	Xen tools within FreeBSD domU

BUILD_DEPENDS=	${LOCALBASE}/bin/bash:shells/bash \
		${LOCALBASE}/lib/libglib-2.0.so:devel/glib20 \
		${LOCALBASE}/lib/libargp.so:devel/argp-standalone \
		${LOCALBASE}/lib/libyajl.so:devel/yajl

ONLY_FOR_ARCHS=		amd64 i386 ia64
ONLY_FOR_ARCHS_REASON=	"not yet ported to anything other than amd64, i386, or ia64"
CONFLICTS=	xen-tools-[0-9]*

USES=		gmake python:configure perl5 gettext-runtime:build gettext-tools:build pkgconfig
USE_PERL5=	build
GNU_CONFIGURE=	yes
CONFIGURE_ENV+=	PYTHON=${PYTHON_CMD} PYTHON_PATH=${PYTHON_CMD}
CONFIGURE_ENV+=	APPEND_LIB="${LOCALBASE}/lib"
CPPFLAGS+=	-I${LOCALBASE}/include
LDFLAGS+=	-I${LOCALBASE}/lib
USE_LDCONFIG=	yes

PLIST_FILES=	lib/libxenstore.so.3.0 \
		bin/xen-detect \
		bin/xenstore \
		bin/xenstore-control \
		bin/xenstore-chmod \
		bin/xenstore-exists \
		bin/xenstore-list \
		bin/xenstore-ls \
		bin/xenstore-read \
		bin/xenstore-rm \
		bin/xenstore-write

post-patch:
	${REINPLACE_CMD} -e 's;86|x86_64;86no|x86_64no;' \
		${WRKSRC}/tools/configure

do-build:
	cd ${WRKSRC}/tools && ${SETENV} ${MAKE_ENV} ${MAKE_CMD} -C include
	cd ${WRKSRC}/tools/misc && ${SETENV} ${MAKE_ENV} ${MAKE_CMD} xen-detect
	cd ${WRKSRC}/tools/xenstore && ${SETENV} ${MAKE_ENV} ${MAKE_CMD} clients

do-install:
	${INSTALL_PROGRAM} ${WRKSRC}/tools/misc/xen-detect ${STAGEDIR}${PREFIX}/bin
	${INSTALL_PROGRAM} ${WRKSRC}/tools/xenstore/xenstore ${STAGEDIR}${PREFIX}/bin
	${INSTALL_PROGRAM} ${WRKSRC}/tools/xenstore/xenstore-control ${STAGEDIR}${PREFIX}/bin
	${INSTALL_PROGRAM} ${WRKSRC}/tools/xenstore/libxenstore.so.3.0 ${STAGEDIR}${PREFIX}/lib
	${LN} -sf ${PREFIX}/bin/xenstore ${STAGEDIR}${PREFIX}/bin/xenstore-chmod
	${LN} -sf ${PREFIX}/bin/xenstore ${STAGEDIR}${PREFIX}/bin/xenstore-exists
	${LN} -sf ${PREFIX}/bin/xenstore ${STAGEDIR}${PREFIX}/bin/xenstore-list
	${LN} -sf ${PREFIX}/bin/xenstore ${STAGEDIR}${PREFIX}/bin/xenstore-ls
	${LN} -sf ${PREFIX}/bin/xenstore ${STAGEDIR}${PREFIX}/bin/xenstore-read
	${LN} -sf ${PREFIX}/bin/xenstore ${STAGEDIR}${PREFIX}/bin/xenstore-rm
	${LN} -sf ${PREFIX}/bin/xenstore ${STAGEDIR}${PREFIX}/bin/xenstore-write

.include <bsd.port.mk>
