# $FreeBSD$

PORTNAME=	libhyve-remote
PORTVERSION=	0.1.4.1
CATEGORIES=	devel

MAINTAINER=	araujo@FreeBSD.org
COMMENT=	Library to abstract vnc, rdp and spice protocols

LICENSE=	BSD2CLAUSE GPLv2
LICENSE_COMB=	dual

LIB_DEPENDS=	libvncserver.so:net/libvncserver

OPTIONS_DEFINE=	BHYVE
BHYVE_DESC=	FreeBSD bhyve libhyve-remote integration

CFLAGS+=	-I${LOCALBASE}/include
LDFLAGS+=	-L${LOCALBASE}/lib

PLIST_FILES=	${HEADER_FILES} \
		${LIB_FILES}

HEADER_FILES=	include/libhyverem/hyverem.h	\
		include/libhyverem/rfbsrv.h	\
		include/libhyverem/libcheck.h	\
		include/libhyverem/vncserver.h

LIB_FILES=	lib/libhyverem.so.1	\
		lib/libhyverem.so	\
		lib/libhyverem.a	\
		lib/libhyverem_p.a
PLIST_DIRS=	${LOCALBASE}/include/libhyverem

USE_GITHUB=	yes
GH_ACCOUNT=	araujobsd

USE_LDCONFIG=	yes

.include <bsd.port.options.mk>

do-install:
	${MKDIR} ${STAGEDIR}${PREFIX}/include/libhyverem
.for headers in ${HEADER_FILES}
	${INSTALL_DATA} ${WRKSRC}/include/${headers:T} ${STAGEDIR}${PREFIX}/include/libhyverem/${headers:T}
.endfor
.for lib in ${LIB_FILES:T}
	${INSTALL_DATA} ${WRKSRC}/${lib} ${STAGEDIR}${PREFIX}/lib/
.endfor
	${STRIP_CMD} ${STAGEDIR}${PREFIX}/lib/*.so.1
	${LN} -fs libhyverem.so.1 ${STAGEDIR}${PREFIX}/lib/libhyverem.so

post-install:
.if ${PORT_OPTIONS:MBHYVE}
.if !exists(${SRC_BASE}/usr.sbin/bhyve/pci_fbuf.c)
IGNORE=	requires kernel source files in ${SRC_BASE}
.else
	(cd ${WRKSRC} && ${MAKE_CMD} bhyve-patch)
.endif
.endif

.include <bsd.port.mk>
