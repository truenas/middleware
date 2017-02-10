# $FreeBSD: head/www/minio/Makefile 429568 2016-12-26 19:36:25Z swills $

PORTNAME=	minio
PORTVERSION=	2017.01.25.03.14.52
CATEGORIES=	www

MAINTAINER=	swills@FreeBSD.org
COMMENT=	Amazon S3 compatible object storage server

BUILD_DEPENDS=	go>=1.7:lang/go \
		bash:shells/bash

USES=		gmake

USE_GITHUB=	yes
GH_TAGNAME=	RELEASE.2017-01-25T03-14-52Z
GH_SUBDIR=	src/github.com/${GH_ACCOUNT}/${PORTNAME}
MAKE_ENV=	GOPATH=${WRKSRC} GOROOT=${LOCALBASE}/go

STRIP=		# stripping can break go binaries
PLIST_FILES=	bin/minio

USE_RC_SUBR=	minio

do-install:
	${INSTALL_PROGRAM} ${WRKSRC}/src/github.com/${GH_ACCOUNT}/${PORTNAME}/bin/${PORTNAME} ${STAGEDIR}${PREFIX}/bin/${PORTNAME}

.include <bsd.port.mk>
