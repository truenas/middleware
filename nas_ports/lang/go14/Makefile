# $FreeBSD: head/lang/go14/Makefile 424106 2016-10-17 10:50:57Z linimon $

PORTNAME=	go14
PORTVERSION=	1.4.3
CATEGORIES=	lang
MASTER_SITES=	http://golang.org/dl/
DISTNAME=	go${PORTVERSION}.src

MAINTAINER=	jlaffaye@FreeBSD.org
COMMENT=	Go programming language

LICENSE=	BSD3CLAUSE

USES=		compiler shebangfix
SHEBANG_LANG=	sh
SHEBANG_FILES=	${WRKSRC}/src/*.bash \
		${WRKSRC}/doc/progs/run \
		${WRKSRC}/doc/articles/wiki/*.bash \
		${WRKSRC}/test/bench/shootout/timing.sh

sh_OLD_CMD=	"/usr/bin/env bash"
sh_CMD=		${SH}

WRKSRC=		${WRKDIR}/go
ONLY_FOR_ARCHS=	i386 amd64 armv6 armv6hf

# NB: apparently this failure is only when running under emulation via
# qemu; it works fine on native hardware.  Let's leave the line in as a
# reminder, but commented out for now while this is being investigated.
#BROKEN_armv6=		Fails to configure: wait: interrupted system call

.include <bsd.port.pre.mk>

# If cc is clang, change it to clang to help Go identify the compiler
.if ${COMPILER_TYPE} == "clang" && ${CC} == "cc"
CC=clang
.endif

.if ${ARCH} == "i386"
GOARCH=386
GOOBJ=8
.elif ${ARCH} == "amd64"
GOARCH=amd64
GOOBJ=6
.elif ${ARCH} == "armv6" || ${ARCH} == "armv6hf"
GOARCH=arm
GOOBJ=5
.else
IGNORE=		unknown arch ${ARCH}
.endif

PLIST_SUB+=	ARCH=${GOARCH} \
		GOOBJ=${GOOBJ}

post-patch:
	@cd ${WRKSRC} && ${FIND} . -name '*.orig' -delete

do-build:
	cd ${WRKSRC}/src && \
		CC=${CC} \
		GOROOT=${WRKSRC} GOROOT_FINAL=${PREFIX}/go14 \
		GOBIN= GOARCH=${GOARCH} GOOS=${OPSYS:tl} \
		CGO_ENABLED=0 \
		${SH} make.bash

do-install:
	@${CP} -a ${WRKSRC} ${STAGEDIR}${PREFIX}/go14

regression-test: build
	cd ${WRKSRC}/src && GOROOT=${WRKSRC} PATH=${WRKSRC}/bin:${PATH} ${SH} run.bash --no-rebuild --banner

.include <bsd.port.post.mk>
