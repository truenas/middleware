# $FreeBSD: head/www/minio/Makefile 429568 2016-12-26 19:36:25Z swills $

PORTNAME=	minio
PORTVERSION=	2017.02.16.01.47.30
CATEGORIES=	www

MAINTAINER=	swills@FreeBSD.org
COMMENT=	Amazon S3 compatible object storage server

LICENSE=	APACHE20

BUILD_DEPENDS=	go>=1.7:lang/go \
		bash:shells/bash

USES=	compiler go

USE_GITHUB=	yes
GH_TAGNAME=	RELEASE.2017-02-16T01-47-30Z
GH_SUBDIR=	src/github.com/minio/minio
GH_TUPLE=	\
	hashicorp:go-version:03c5bf6:go_version/src/github.com/hashicorp/go-version \
	minio:mc:RELEASE.2017-02-06T20-16-19Z:mc/src/github.com/minio/mc
MAKE_ENV=	GOPATH=${WRKSRC} GOROOT=${LOCALBASE}/go

STRIP=		# stripping can break go binaries
PLIST_FILES=	bin/minio

USE_RC_SUBR=	minio

USERS=	minio
GROUPS=	minio

do-build:
	cd ${GO_WRKSRC}; ${SETENV} ${MAKE_ENV} \
		go build -ldflags "-X main.GitDescribe=${DISTVERSIONFULL}" -o bin/minio

do-install:
	${INSTALL_PROGRAM} ${WRKSRC}/src/github.com/${GH_ACCOUNT}/${PORTNAME}/bin/${PORTNAME} ${STAGEDIR}${PREFIX}/bin/${PORTNAME}

.include <bsd.port.pre.mk>

.if ${COMPILER_TYPE} == clang
BUILD_ENV=  CC=clang
.endif

.include <bsd.port.post.mk>
