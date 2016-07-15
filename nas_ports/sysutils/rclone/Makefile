# $FreeBSD$

PORTNAME=	rclone
PORTVERSION=	1.26
DISTVERSIONPREFIX=      v
PORTREVISION=   1
CATEGORIES=	sysutils

MAINTAINER=     jmaloney@pcbsd.org
COMMENT=        Sync files to and from various cloud services

LICENSE=	MIT

BUILD_DEPENDS=  ${LOCALBASE}/bin/go:${PORTSDIR}/lang/go

USE_GITHUB=     yes
GH_ACCOUNT=     ncw:DEFAULT,swift,goacd Unknwon:goconfig spf13:pflag stacktic:dropbox tsenart:tb VividCortex:ewma aws:awssdkgo mreiferson:gohttpclient skratchdot:opengolang go-ini:ini google:goquerystring jmespath:gojmespath golang:oauth2 google:googleapigoclient GoogleCloudPlatform:gcloudgolang golang:net
GH_PROJECT=     swift:swift go-acd:goacd goconfig:goconfig pflag:pflag dropbox:dropbox tb:tb ewma:ewma aws-sdk-go:awssdkgo go-httpclient:gohttpclient open-golang:opengolang ini:ini go-querystring:goquerystring go-jmespath:gojmespath oauth2:oauth2 google-api-go-client:googleapigoclient gcloud-golang:gcloudgolang net:net
GH_TAGNAME=     eb694f7:swift 2a07313:goacd 18bc852:goconfig 7f60f83:pflag b7d75fe:dropbox 19f4c3d:tb c34099b:ewma 87b1e60:awssdkgo 63fe23f:gohttpclient c874831:opengolang afbd495:ini 2a60fc2:goquerystring c01cf91:gojmespath 8a57ed9:oauth2 0caa379:googleapigoclient 777d8f0:gcloudgolang f315505:net

STRIP=          # stripping can break go binaries

post-extract:
	@${MKDIR} ${WRKSRC}/src/github.com/${GH_ACCOUNT}/${PORTNAME}
.for src in amazonclouddrive b2 dircache docs drive dropbox fs fstest googlecloudstorage graphics hubic local oauthutil onedrive pacer rest s3 swift yandex CONTRIBUTING.md COPYING README.md appveyor.yml rclone.go redirect_stderr.go redirect_stderr_unix.go
	@${MV} ${WRKSRC}/${src} \
		${WRKSRC}/src/github.com/ncw/${PORTNAME}
.endfor
	@${MKDIR} ${WRKSRC}/src/github.com/Unknwon
	@${MKDIR} ${WRKSRC}/src/github.com/spf13
	@${MKDIR} ${WRKSRC}/src/github.com/stacktic
	@${MKDIR} ${WRKSRC}/src/github.com/tsenart
	@${MKDIR} ${WRKSRC}/src/github.com/VividCortex
	@${MKDIR} ${WRKSRC}/src/github.com/aws
	@${MKDIR} ${WRKSRC}/src/github.com/mreiferson
	@${MKDIR} ${WRKSRC}/src/github.com/skratchdot
	@${MKDIR} ${WRKSRC}/src/github.com/go-ini
	@${MKDIR} ${WRKSRC}/src/github.com/google
	@${MKDIR} ${WRKSRC}/src/github.com/jmespath
	@${MKDIR} ${WRKSRC}/src/golang.org/x
	@${MKDIR} ${WRKSRC}/src/google.golang.org
	@${MV} ${WRKSRC_swift} ${WRKSRC}/src/github.com/ncw/swift
	@${MV} ${WRKSRC_goacd} ${WRKSRC}/src/github.com/ncw/go-acd
	@${MV} ${WRKSRC_goconfig} ${WRKSRC}/src/github.com/Unknwon/goconfig
	@${MV} ${WRKSRC_pflag} ${WRKSRC}/src/github.com/spf13/pflag
	@${MV} ${WRKSRC_dropbox} ${WRKSRC}/src/github.com/stacktic/dropbox
	@${MV} ${WRKSRC_tb} ${WRKSRC}/src/github.com/tsenart/tb
	@${MV} ${WRKSRC_ewma} ${WRKSRC}/src/github.com/VividCortex/ewma
	@${MV} ${WRKSRC_awssdkgo} ${WRKSRC}/src/github.com/aws/aws-sdk-go
	@${MV} ${WRKSRC_gohttpclient} ${WRKSRC}/src/github.com/mreiferson/go-httpclient
	@${MV} ${WRKSRC_opengolang} ${WRKSRC}/src/github.com/skratchdot/open-golang
	@${MV} ${WRKSRC_ini} ${WRKSRC}/src/github.com/go-ini/ini
	@${MV} ${WRKSRC_goquerystring} ${WRKSRC}/src/github.com/google/go-querystring
	@${MV} ${WRKSRC_gojmespath} ${WRKSRC}/src/github.com/jmespath/go-jmespath
	@${MV} ${WRKSRC_oauth2} ${WRKSRC}/src/golang.org/x/oauth2
	@${MV} ${WRKSRC_googleapigoclient} ${WRKSRC}/src/google.golang.org/api
	@${MV} ${WRKSRC_gcloudgolang} ${WRKSRC}/src/google.golang.org/cloud
	@${MV} ${WRKSRC_net} ${WRKSRC}/src/golang.org/x/net

do-build:
	@cd ${WRKSRC}/src/github.com/${GH_ACCOUNT}/${PORTNAME}; ${SETENV} GOPATH=${WRKSRC} go build rclone.go redirect_stderr.go
do-install:
	${INSTALL_PROGRAM} ${WRKSRC}/src/github.com/${GH_ACCOUNT}/${PORTNAME}/${PORTNAME} ${STAGEDIR}${PREFIX}/bin/${PORTNAME}

.include <bsd.port.mk>
