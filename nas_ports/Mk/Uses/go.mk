# $FreeBSD: head/Mk/Uses/go.mk 413776 2016-04-22 12:40:04Z mat $
#
# This file contains logic to ease porting of Go packages or binaries using
# the `go` command.
#
# Feature:	go
# Usage:	USES=go
# Valid ARGS:	none
#
# You can set the following variables to control the process.
#
# GO_PKGNAME
#	The name of the package. This is the directory that will be
# 	created in GOPATH/src and seen by the `go` command
#
# GO_TARGET
#	The names of the package(s) to build
#
# CGO_CFLAGS
#	Addional CFLAGS variables to be passed to the C compiler by the `go`
#	command
#
# CGO_LDFLAGS
#	Addional LDFLAGS variables to be passed to the C compiler by the `go`
#	command
#
# MAINTAINER: jlaffaye@FreeBSD.org

.if !defined(_INCLUDE_USES_GO_MK)
_INCLUDE_USES_GO_MK=	yes

.if ${ARCH} == "i386"
GOARCH=	386
GOOBJ=	8
.else
GOARCH=	amd64
GOOBJ=	6
.endif

# Settable variables
GO_PKGNAME?=	${PORTNAME}
GO_TARGET?=	${GO_PKGNAME}
CGO_CFLAGS+=	-I${LOCALBASE}/include
CGO_LDFLAGS+=	-L${LOCALBASE}/lib

# Read-only variables
GO_CMD=		${LOCALBASE}/bin/go
LOCAL_GOPATH=	${LOCALBASE}/share/go
GO_LIBDIR=	share/go/pkg/${OPSYS:tl}_${GOARCH}
GO_SRCDIR=	share/go/src
GO_WRKSRC=	${GO_WRKDIR_SRC}/${GO_PKGNAME}
GO_WRKDIR_BIN=	${WRKDIR}/bin
GO_WRKDIR_SRC=	${WRKDIR}/src
GO_WRKDIR_PKG=	${WRKDIR}/pkg/${OPSYS:tl}_${GOARCH}

BUILD_DEPENDS+=	${GO_CMD}:lang/go
GO_ENV+=	GOPATH="${WRKDIR}:${LOCAL_GOPATH}" \
		CGO_CFLAGS="${CGO_CFLAGS}" \
		CGO_LDFLAGS="${CGO_LDFLAGS}" \
		GOBIN=""
PLIST_SUB+=	GO_LIBDIR=${GO_LIBDIR} \
		GO_SRCDIR=${GO_SRCDIR} \
		GO_PKGNAME=${GO_PKGNAME}

.if !target(post-extract)
post-extract:
	@${MKDIR} ${GO_WRKSRC:H}
	@${LN} -sf ${WRKSRC} ${GO_WRKSRC}
.endif

.if !target(do-build)
do-build:
	@(cd ${GO_WRKSRC}; ${SETENV} ${MAKE_ENV} ${GO_ENV} ${GO_CMD} install -v ${GO_TARGET})
.endif

.if !target(do-install)
do-install:
.for _TARGET in ${GO_TARGET}
	@if [ -e "${GO_WRKDIR_PKG}/${_TARGET}.a" ]; then \
		_TARGET_LIBDIR="${STAGEDIR}/${PREFIX}/${GO_LIBDIR}/${_TARGET:H}"; \
		${MKDIR} $${_TARGET_LIBDIR}; \
		${INSTALL_DATA} ${GO_WRKDIR_PKG}/${_TARGET}.a $${_TARGET_LIBDIR}; \
		_TARGET_SRCDIR="${STAGEDIR}/${PREFIX}/${GO_SRCDIR}/${_TARGET}"; \
		${MKDIR} $${_TARGET_SRCDIR}; \
		(cd ${GO_WRKDIR_SRC}/${_TARGET}/ && ${COPYTREE_SHARE} \* $${_TARGET_SRCDIR}); \
	fi; \
	if [ -e "${GO_WRKDIR_BIN}/${_TARGET:T}" ]; then \
		${INSTALL_PROGRAM} ${GO_WRKDIR_BIN}/${_TARGET:T} ${STAGEDIR}/${LOCALBASE}/bin; \
	fi;
.endfor
.endif

.endif
