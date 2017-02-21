# $FreeBSD$

PORTNAME=	minio-client
PORTVERSION=	2017.02.06.20.16.19
PORTREVISION=	1
CATEGORIES=	misc

MAINTAINER=	jhixson@gmail.com
COMMENT=	Replacement for ls, cp, mkdir, diff and rsync commands for filesystems and object storage

LICENSE=	APACHE20

BUILD_DEPENDS=	go>=1.7:lang/go \
		bash:shells/bash

USE_GITHUB=	yes
GH_ACCOUNT=	minio
GH_PROJECT=	mc
GH_TAGNAME=	RELEASE.2017-02-06T20-16-19Z
GH_SUBDIR=	src/github.com/${GH_ACCOUNT}/${GH_PROJECT}
MAKE_ENV=	GOPATH=${WRKSRC} GOROOT=${LOCALBASE}/go

STRIP=		# stripping can break go binaries
PLIST_FILES=	bin/${PORTNAME}

do-build:
	@cd ${WRKSRC}/src/github.com/${GH_ACCOUNT}/${GH_PROJECT}; \
	${SETENV} ${BUILD_ENV} GOPATH=${WRKSRC} go build -v -x \
		-ldflags "-X main.GitDescribe=v${PORTVERSION}" -o bin/${PORTNAME}

do-install:
	${INSTALL_PROGRAM} ${WRKSRC}/src/github.com/${GH_ACCOUNT}/${GH_PROJECT}/bin/${PORTNAME} \
		${STAGEDIR}${PREFIX}/bin/${PORTNAME}

.include <bsd.port.mk>
