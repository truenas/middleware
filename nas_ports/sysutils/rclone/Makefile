# $FreeBSD: head/net/rclone/Makefile 422696 2016-09-23 20:29:58Z wg $

PORTNAME=	rclone
PORTVERSION=	1.33
DISTVERSIONPREFIX=      v
CATEGORIES=	net

MAINTAINER=     wg@FreeBSD.org
COMMENT=        Sync files to and from various cloud services

LICENSE=	MIT

USES=		go
USE_GITHUB=     yes
GH_TUPLE+=	\
		ncw:rclone:${DISTVERSIONFULL} \
		ncw:go-acd:56da839:goacd \
		ncw:swift:b964f2c:swift \
		aws:aws-sdk-go:87a2cff:awssdkgo \
		mreiferson:go-httpclient:31f0106:gohttpclient \
		google:go-querystring:9235644:goquerystring \
		GoogleCloudPlatform:google-cloud-go:80a7732:gcloudgolang \
		google:google-api-go-client:0caa379:googleapigoclient \
		golang:oauth2:3c3a985:oauth2 \
		golang:net:6d3beae:net \
		golang:text:a7c0236:text \
		skratchdot:open-golang:75fb7ed:opengolang \
		stacktic:dropbox:58f839b:dropbox \
		tsenart:tb:19f4c3d:tb \
		VividCortex:ewma:c595cd8:ewma \
		golang:crypto:8e06e8d:crypto \
		pkg:errors:a887431:errors \
		bazil:fuse:371fbbd:fuse \
		spf13:cobra:9c28e4b:cobra \
		spf13:pflag:c7e63cf:pflag \
		rfjakob:eme:601d0e2:eme \
		ogier:pflag:45c278a:opflag \
		Unknwon:goconfig:5aa4f8c:goconfig \
		cpuguy83:go-md2man:a65d4d2:gomd2man

PLIST_FILES=	bin/rclone

STRIP=          # stripping can break go binaries

post-extract:
	@${MKDIR} ${WRKSRC}/src/github.com/${GH_ACCOUNT}/${PORTNAME}
.for src in amazonclouddrive b2 cmd crypt dircache docs drive dropbox fs fstest googlecloudstorage graphics hubic local oauthutil onedrive pacer rest s3 swift yandex CONTRIBUTING.md COPYING README.md appveyor.yml rclone.go
	@${MV} ${WRKSRC}/${src} \
		${WRKSRC}/src/github.com/ncw/${PORTNAME}
.endfor
	@${MKDIR} ${WRKSRC}/src/bazil.org
	@${MKDIR} ${WRKSRC}/src/github.com/Unknwon
	@${MKDIR} ${WRKSRC}/src/github.com/cpuguy83
	@${MKDIR} ${WRKSRC}/src/github.com/ogier
	@${MKDIR} ${WRKSRC}/src/github.com/rfjakob
	@${MKDIR} ${WRKSRC}/src/github.com/spf13
	@${MKDIR} ${WRKSRC}/src/github.com/stacktic
	@${MKDIR} ${WRKSRC}/src/github.com/tsenart
	@${MKDIR} ${WRKSRC}/src/github.com/VividCortex
	@${MKDIR} ${WRKSRC}/src/github.com/aws
	@${MKDIR} ${WRKSRC}/src/github.com/mreiferson
	@${MKDIR} ${WRKSRC}/src/github.com/skratchdot
	@${MKDIR} ${WRKSRC}/src/github.com/google
	@${MKDIR} ${WRKSRC}/src/github.com/pkg
	@${MKDIR} ${WRKSRC}/src/golang.org/x
	@${MKDIR} ${WRKSRC}/src/cloud.google.com
	@${MKDIR} ${WRKSRC}/src/google.golang.org
	@${MV} ${WRKSRC_fuse} ${WRKSRC}/src/bazil.org/fuse
	@${MV} ${WRKSRC_swift} ${WRKSRC}/src/github.com/ncw/swift
	@${MV} ${WRKSRC_goacd} ${WRKSRC}/src/github.com/ncw/go-acd
	@${MV} ${WRKSRC_goconfig} ${WRKSRC}/src/github.com/Unknwon/goconfig
	@${MV} ${WRKSRC_gomd2man} ${WRKSRC}/src/github.com/cpuguy83/go-md2man
	@${MV} ${WRKSRC_opflag} ${WRKSRC}/src/github.com/ogier/pflag
	@${MV} ${WRKSRC_eme} ${WRKSRC}/src/github.com/rfjakob/eme
	@${MV} ${WRKSRC_cobra} ${WRKSRC}/src/github.com/spf13/cobra
	@${MV} ${WRKSRC_pflag} ${WRKSRC}/src/github.com/spf13/pflag
	@${MV} ${WRKSRC_dropbox} ${WRKSRC}/src/github.com/stacktic/dropbox
	@${MV} ${WRKSRC_tb} ${WRKSRC}/src/github.com/tsenart/tb
	@${MV} ${WRKSRC_ewma} ${WRKSRC}/src/github.com/VividCortex/ewma
	@${MV} ${WRKSRC_awssdkgo} ${WRKSRC}/src/github.com/aws/aws-sdk-go
	@${MV} ${WRKSRC_gohttpclient} ${WRKSRC}/src/github.com/mreiferson/go-httpclient
	@${MV} ${WRKSRC_opengolang} ${WRKSRC}/src/github.com/skratchdot/open-golang
	@${MV} ${WRKSRC_goquerystring} ${WRKSRC}/src/github.com/google/go-querystring
	@${MV} ${WRKSRC_errors} ${WRKSRC}/src/github.com/pkg/errors
	@${MV} ${WRKSRC_oauth2} ${WRKSRC}/src/golang.org/x/oauth2
	@${MV} ${WRKSRC_googleapigoclient} ${WRKSRC}/src/google.golang.org/api
	@${MV} ${WRKSRC_gcloudgolang} ${WRKSRC}/src/cloud.google.com/go
	@${MV} ${WRKSRC_net} ${WRKSRC}/src/golang.org/x/net
	@${MV} ${WRKSRC_text} ${WRKSRC}/src/golang.org/x/text
	@${MV} ${WRKSRC_crypto} ${WRKSRC}/src/golang.org/x/crypto

do-build:
	@cd ${WRKSRC}/src/github.com/${GH_ACCOUNT}/${PORTNAME}; ${SETENV} GOPATH=${WRKSRC} go build .

do-install:
	${INSTALL_PROGRAM} ${WRKSRC}/src/github.com/${GH_ACCOUNT}/${PORTNAME}/${PORTNAME} ${STAGEDIR}${PREFIX}/bin/${PORTNAME}

.include <bsd.port.mk>
