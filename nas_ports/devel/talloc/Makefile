# $FreeBSD$

PORTNAME=		talloc
PORTVERSION=		2.1.8
PORTREVISION=		0
PORTEPOCH=		0
CATEGORIES=		devel
MASTER_SITES=		SAMBA

MAINTAINER=		timur@FreeBSD.org
COMMENT=		Hierarchical pool based memory allocator

LICENSE=		LGPL3

CONFLICTS=		samba33-3.*

USES=			compiler pkgconfig waf
USE_LDCONFIG=		yes
WAF_CMD=		buildtools/bin/waf
CONFIGURE_LOG=		bin/config.log

PKGCONFIGDIR?=		${PREFIX}/libdata/pkgconfig
PLIST_SUB+=		PKGCONFIGDIR=${PKGCONFIGDIR:S;${PREFIX}/;;}

CONFIGURE_ARGS+=	--mandir=${MANPREFIX}/man \
			--infodir=${PREFIX}/${INFO_PATH}/${INFO_SUBDIR} \
			--disable-rpath \
			--without-gettext

OPTIONS_DEFINE=		MANPAGES
MANPAGES_DESC=		Build and install manpages (requires textproc/docbook-xsl)

.include <bsd.port.options.mk>

.if defined(NO_PYTHON)
CONFIGURE_ARGS+=	--disable-python
.else
USES+=			python:2
PLIST_FILES+=		include/pytalloc.h \
			lib/libpytalloc-util.so \
			lib/libpytalloc-util.so.2 \
			%%PYTHON_SITELIBDIR%%/talloc.so \
			%%PKGCONFIGDIR%%/pytalloc-util.pc
.endif

.include <bsd.port.pre.mk>

.if ! ${PORT_OPTIONS:MMANPAGES}
CONFIGURE_ENV+=		XSLTPROC="true"
.else
BUILD_DEPENDS+=		${LOCALBASE}/share/xsl/docbook/manpages/docbook.xsl:textproc/docbook-xsl \
			xsltproc:textproc/libxslt
.endif

PLIST_FILES+=		include/talloc.h \
			lib/libtalloc.so \
			lib/libtalloc.so.2 \
			%%PKGCONFIGDIR%%/talloc.pc

# No fancy color error messages
.if ${COMPILER_TYPE} == "clang"
CFLAGS+=		-fno-color-diagnostics
.endif
CONFIGURE_ENV+=		NOCOLOR=yes
MAKE_ENV+=		NOCOLOR=yes

TALLOC_MAN3=		man/man3/talloc.3.gz

PLIST_FILES+=		${TALLOC_MAN3}

IGNORE_NONTHREAD_PYTHON=needs port lang/python${PYTHON_SUFFIX} to be build with THREADS support

post-patch:
			@${REINPLACE_CMD} -e 's|%%PKGCONFIGDIR%%|${PKGCONFIGDIR}|g' \
				${BUILD_WRKSRC}/wscript

# Use threading (or multiprocessing) but not thread (renamed in python 3+).
pre-configure:
			@if ! ${PYTHON_CMD} -c "import multiprocessing;" 2>/dev/null; then \
				${ECHO_CMD}; \
				${ECHO_MSG} "===>  ${PKGNAME} "${IGNORE_NONTHREAD_PYTHON:Q}.; \
				${ECHO_CMD}; \
				${FALSE}; \
			fi

pre-build:
.if ! ${PORT_OPTIONS:MMANPAGES}
			-${MKDIR} ${BUILD_WRKSRC}/bin/default/man
.	for man in ${TALLOC_MAN3}
			${INSTALL_MAN} ${FILESDIR}/`basename ${man} .gz` ${BUILD_WRKSRC}/bin/default/man
.	endfor
.endif

.include <bsd.port.post.mk>
