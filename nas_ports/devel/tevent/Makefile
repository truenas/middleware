# $FreeBSD$

PORTNAME=		tevent
PORTVERSION=		0.9.31
PORTREVISION=		0
PORTEPOCH=		0
CATEGORIES=		devel
MASTER_SITES=		SAMBA

MAINTAINER=		timur@FreeBSD.org
COMMENT=		Talloc based event loop library

LICENSE=		LGPL3

CONFLICTS=

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

BUILD_DEPENDS+=		talloc>=2.1.5:devel/talloc
RUN_DEPENDS:=		${BUILD_DEPENDS}

.include <bsd.port.options.mk>

.if defined(NO_PYTHON)
CONFIGURE_ARGS+=	--disable-python
.else
USES+=			python:2
PLIST_FILES+=		%%PYTHON_SITELIBDIR%%/_tevent.so \
			%%PYTHON_SITELIBDIR%%/tevent.py  \
			%%PYTHON_SITELIBDIR%%/tevent.pyc \
			%%PYTHON_SITELIBDIR%%/tevent.pyo
.endif

.include <bsd.port.pre.mk>

.if ! ${PORT_OPTIONS:MMANPAGES}
CONFIGURE_ENV+=		XSLTPROC="true"
.else
BUILD_DEPENDS+=		${LOCALBASE}/share/xsl/docbook/manpages/docbook.xsl:textproc/docbook-xsl \
			xsltproc:textproc/libxslt
.endif

PLIST_FILES+=		include/tevent.h \
			lib/libtevent.so \
			lib/libtevent.so.0 \
			%%PKGCONFIGDIR%%/tevent.pc

CONFIGURE_ARGS+=	--bundled-libraries=!talloc

# No fancy color error messages
.if ${COMPILER_TYPE} == "clang"
CFLAGS+=		-fno-color-diagnostics
.endif
CONFIGURE_ENV+=		NOCOLOR=yes
MAKE_ENV+=		NOCOLOR=yes

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

post-build:
			${PYTHON_CMD} -m py_compile ${BUILD_WRKSRC}/tevent.py
			${PYTHON_CMD} -O -m py_compile ${BUILD_WRKSRC}/tevent.py

.include <bsd.port.post.mk>
