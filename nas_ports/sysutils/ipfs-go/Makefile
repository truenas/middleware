# $FreeBSD$

PORTNAME=	ipfs-go
PORTVERSION=	0.4.7
DISTVERSIONPREFIX=	v
CATEGORIES=	sysutils

MAINTAINER=	jhixson@gmail.com
COMMENT=	IPFS implementation in Go

LICENSE=	MIT

BUILD_DEPENDS=	go>=1.7:lang/go

ONLY_FOR_ARCHS=	amd64

USES=		compiler go

USE_GITHUB=	yes
GH_ACCOUNT=	jhixson74

MAKE_ENV+=	GOPATH=${WRKSRC}

PLIST_FILES=	bin/${PORTNAME}

USE_RC_SUBR=	${PORTNAME}

STRIP=		# stripping can break go binaries

do-build:
	cd ${WRKSRC}/src/github.com/ipfs/go-ipfs/cmd/ipfs; \
		${SETENV} ${BUILD_ENV} ${MAKE_ENV} go build -v -x \
			-ldflags "-X main.GitDescribe=${DISTVERSIONFULL}" -o bin/${PORTNAME}

do-install:
	${INSTALL_PROGRAM} ${WRKSRC}/src/github.com/ipfs/go-ipfs/cmd/ipfs/bin/${PORTNAME} ${STAGEDIR}${PREFIX}/bin/${PORTNAME}

.include <bsd.port.pre.mk>

.if ${COMPILER_TYPE} == clang
BUILD_ENV=  CC=clang
.endif

.include <bsd.port.post.mk>
