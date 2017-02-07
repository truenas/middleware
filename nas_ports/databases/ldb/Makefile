# $FreeBSD: head/databases/ldb/Makefile 413162 2016-04-12 22:40:36Z timur $

PORTNAME=		ldb
PORTVERSION=		1.1.29
PORTREVISION=		0
PORTEPOCH=		0
CATEGORIES=		databases
MASTER_SITES=		SAMBA

MAINTAINER=		timur@FreeBSD.org
COMMENT=		LDAP-like embedded database

LICENSE=		GPLv3

CONFLICTS=		*samba3[0-4]-3.*

USES=			compiler pkgconfig python:2 waf
USE_LDCONFIG=		yes
WAF_CMD=		buildtools/bin/waf
CONFIGURE_LOG=		bin/config.log

USE_OPENLDAP=		yes

PKGCONFIGDIR?=		${PREFIX}/libdata/pkgconfig
PLIST_SUB+=		PKGCONFIGDIR=${PKGCONFIGDIR:S;${PREFIX}/;;}

CONFIGURE_ARGS+=	--mandir=${MANPREFIX}/man \
			--infodir=${PREFIX}/${INFO_PATH}/${INFO_SUBDIR} \
			--disable-rpath \
			--without-gettext

OPTIONS_DEFINE=		MANPAGES
MANPAGES_DESC=		Build and install manpages (requires textproc/docbook-xsl)

BUILD_DEPENDS+=		talloc>=2.1.5:devel/talloc \
			tevent>=0.9.27:devel/tevent \
			tdb>=1.3.8,1:databases/tdb \
			popt>=0:devel/popt
RUN_DEPENDS:=		${BUILD_DEPENDS}

CONFIGURE_ARGS+=	--bundled-libraries=!talloc,!tevent,!tdb,!popt \
			--with-modulesdir=${PREFIX}/lib/shared-modules \
			--with-privatelibdir=${PREFIX}/lib/ldb

.include <bsd.port.pre.mk>

.if ! ${PORT_OPTIONS:MMANPAGES}
CONFIGURE_ENV+=		XSLTPROC="true"
.else
BUILD_DEPENDS+=		${LOCALBASE}/share/xsl/docbook/manpages/docbook.xsl:textproc/docbook-xsl \
			xsltproc:textproc/libxslt
.endif

PLIST_FILES=		bin/ldbedit \
			bin/ldbmodify \
			bin/ldbadd \
			bin/ldbdel \
			bin/ldbsearch \
			bin/ldbrename \
			include/ldb_version.h \
			include/ldb_handlers.h \
			include/ldb_errors.h \
			include/ldb.h \
			include/ldb_module.h \
			lib/libldb.so \
			lib/libldb.so.1 \
			lib/ldb/libldb-cmdline.so \
			lib/shared-modules/ldb/asq.so \
			lib/shared-modules/ldb/ldap.so \
			lib/shared-modules/ldb/paged_results.so \
			lib/shared-modules/ldb/paged_searches.so \
			lib/shared-modules/ldb/rdn_name.so \
			lib/shared-modules/ldb/sample.so \
			lib/shared-modules/ldb/server_sort.so \
			lib/shared-modules/ldb/skel.so \
			lib/shared-modules/ldb/tdb.so \
			%%PKGCONFIGDIR%%/ldb.pc

# No fancy color error messages
.if ${COMPILER_TYPE} == "clang"
CFLAGS+=		-fno-color-diagnostics
.endif
CONFIGURE_ENV+=		NOCOLOR=yes
MAKE_ENV+=		NOCOLOR=yes

PLIST_FILES+=		include/pyldb.h \
			lib/libpyldb-util.so \
			lib/libpyldb-util.so.1 \
			%%PYTHON_SITELIBDIR%%/ldb.so \
			%%PYTHON_SITELIBDIR%%/_ldb_text.py \
			%%PKGCONFIGDIR%%/pyldb-util.pc

LDB_MAN1=		man/man1/ldbadd.1.gz \
			man/man1/ldbdel.1.gz \
			man/man1/ldbedit.1.gz \
			man/man1/ldbmodify.1.gz \
			man/man1/ldbrename.1.gz \
			man/man1/ldbsearch.1.gz

LDB_MAN3=		man/man3/ldb.3.gz

PLIST_FILES+=		${LDB_MAN1} ${LDB_MAN3}

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
.	for man in ${LDB_MAN1} ${LDB_MAN3}
			${INSTALL_MAN} ${FILESDIR}/`basename ${man} .gz` ${BUILD_WRKSRC}/bin/default/man
.	endfor
.endif

.include <bsd.port.post.mk>
