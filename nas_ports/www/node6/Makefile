# $FreeBSD: head/www/node6/Makefile 433456 2017-02-05 21:20:24Z tijl $

PORTNAME=	node
PORTVERSION=	6.9.5
DISTVERSIONPREFIX=	v
PORTREVISION=	1
CATEGORIES=	www
MASTER_SITES=	http://nodejs.org/dist/v${PORTVERSION}/
PKGNAMESUFFIX=	6

MAINTAINER=	bradleythughes@fastmail.fm
COMMENT=	V8 JavaScript for client and server (6.x)

LICENSE=	MIT
LICENSE_FILE=	${WRKSRC}/LICENSE

OPTIONS_DEFINE=	BUNDLED_SSL DOCS NLS DTRACE
OPTIONS_DEFAULT=BUNDLED_SSL DTRACE
OPTIONS_SUB=	yes

.if !exists(/usr/sbin/dtrace)
OPTIONS_EXCLUDE+=	DTRACE
.endif

OPTIONS_EXCLUDE_FreeBSD_10=	DTRACE

BUNDLED_SSL_DESC=		Use node.js's bundled OpenSSL implementation #'
BUNDLED_SSL_USES_OFF=		ssl
BUNDLED_SSL_CONFIGURE_OFF+=	--shared-openssl

NLS_CONFIGURE_ON=	--with-intl=system-icu
NLS_LIB_DEPENDS=	libicui18n.so:devel/icu

USES=		compiler:c++11-lib execinfo gmake python:2,build pkgconfig \
		localbase shebangfix

HAS_CONFIGURE=	yes
USE_LDCONFIG=	yes

CONFLICTS_INSTALL=	node[45]-[0-9]* node01[02]-[0-9]* node-[0-9]* node-devel-[0-9]* iojs-[0-9]*

ONLY_FOR_ARCHS=	i386 amd64 armv6
CONFIGURE_ARGS=	--prefix=${PREFIX_RELDEST} \
		--without-npm \
		--shared-cares \
		--shared-libuv \
		--shared-zlib

SHEBANG_FILES=	tools/specialize_node_d.py tools/genv8constants.py

PREFIX_RELDEST=	${PREFIX:S,^${DESTDIR},,}
REINPLACE_ARGS=	-i ''
MAKE_ENV+=	CC.host=${CC} CXX.host=${CXX} LINK.host=${CXX} LINK.target=${CXX}

LIB_DEPENDS+=	libcares.so:dns/c-ares\
		libuv.so:devel/libuv

.include <bsd.port.options.mk>

.if empty(PORT_OPTIONS:MBUNDLED_SSL)

.if ${OPSYS} == FreeBSD && ${OSVERSION} < 1100085 && ${SSL_DEFAULT} == base
IGNORE=		node.js requires openssl 1.0.2, add DEFAULT_VERSIONS+=ssl=openssl to /etc/make.conf or enable BUNDLED_SSL option
.endif

.if !empty(SSL_DEFAULT:Mlibressl*)
IGNORE=		cannot build node.js with LibreSSL. You must enable BUNDLED_SSL
.endif

.endif

.include <bsd.port.pre.mk>

.if ${ARCH} == "armv6"
CONFIGURE_ARGS+=--openssl-no-asm
.endif

.if ${COMPILER_TYPE} == gcc
# GCC does not expose std::snprintf() without this define
CXXFLAGS+=	-D_GLIBCXX_USE_C99
.endif

.if ${PORT_OPTIONS:MDTRACE}
CONFIGURE_ARGS+=	--with-dtrace
.endif

post-patch:
	@${REINPLACE_CMD} -e 's|/usr/local|${LOCALBASE}|' \
		${WRKSRC}/deps/v8/tools/gyp/v8.gyp
	# So many different ways to run python. Fix them all.
	@${REINPLACE_CMD} -e 's|/usr/bin/env python|${PYTHON_CMD}|' \
		${WRKSRC}/configure
	@${FIND} ${WRKSRC} -type f -name '*.gyp*' -print0 \
		| ${XARGS} -0 ${REINPLACE_CMD} \
			-e "s|'python'|'${PYTHON_CMD}'|" \
			-e 's|<!(python |<!(${PYTHON_CMD} |' \
			-e 's|\&\& python |\&\& ${PYTHON_CMD} |'

post-configure:
	# Post-process Makefile and *.mk files created by node-gyp and remove
	# all occurrences of -I${LOCALBASE}/include. C*FLAGS include this
	# before all -I../deps/* for bundled code. This can cause build
	# breakages if the dependency is installed in ${LOCALBASE}. The
	# USES+=localbase # above will ensure that we pick up includes for real
	# external dependencies.
	${FIND} ${WRKSRC}/out -type f -print0 \
		| ${XARGS} -0 ${REINPLACE_CMD} -e "s|-I${LOCALBASE}/include||g"

post-install:
	${STRIP_CMD} ${STAGEDIR}${PREFIX}/bin/node

.include <bsd.port.post.mk>
