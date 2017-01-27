# $FreeBSD$

PORTNAME=		tdb
PORTVERSION=		1.3.12
PORTREVISION=		0
PORTEPOCH=		1
CATEGORIES=		databases
MASTER_SITES=		SAMBA

MAINTAINER=		timur@FreeBSD.org
COMMENT=		Trivial Database

LICENSE=		GPLv3

CONFLICTS=		*samba3[0-4]-3.*

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
PLIST_FILES+=		%%PYTHON_SITELIBDIR%%/tdb.so \
			%%PYTHON_SITELIBDIR%%/_tdb_text.py
.endif

.include <bsd.port.pre.mk>

.if ! ${PORT_OPTIONS:MMANPAGES}
CONFIGURE_ENV+=		XSLTPROC="true"
.else
BUILD_DEPENDS+=		${LOCALBASE}/share/xsl/docbook/manpages/docbook.xsl:textproc/docbook-xsl \
			xsltproc:textproc/libxslt
.endif

PLIST_FILES+=		bin/tdbbackup \
			bin/tdbdump \
			bin/tdbrestore \
			bin/tdbtool \
			include/tdb.h \
			lib/libtdb.so \
			lib/libtdb.so.1 \
			%%PKGCONFIGDIR%%/tdb.pc

# No fancy color error messages
.if ${COMPILER_TYPE} == "clang"
CFLAGS+=		-fno-color-diagnostics
.endif
CONFIGURE_ENV+=		NOCOLOR=yes
MAKE_ENV+=		NOCOLOR=yes

TDB_MAN8=		man/man8/tdbbackup.8.gz \
			man/man8/tdbdump.8.gz \
			man/man8/tdbrestore.8.gz \
			man/man8/tdbtool.8.gz

PLIST_FILES+=		${TDB_MAN8}

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
.	for man in ${TDB_MAN8}
			${INSTALL_MAN} ${FILESDIR}/`basename ${man} .gz` ${BUILD_WRKSRC}/bin/default/man
.	endfor
.endif

.include <bsd.port.post.mk>
