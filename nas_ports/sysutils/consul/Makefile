# $FreeBSD$

PORTNAME=	consul
PORTVERSION=	0.6.4
DISTVERSIONPREFIX=	v
CATEGORIES=	sysutils
MASTER_SITES=	https://releases.hashicorp.com/consul/${PORTVERSION}/:web_ui
DISTFILES=	consul_${PORTVERSION}_web_ui.zip:web_ui

MAINTAINER=	swills@FreeBSD.org
COMMENT=	Service discovery and configuration made easy

LICENSE=	MPL

BUILD_DEPENDS=	${LOCALBASE}/bin/go:lang/go

USES=		compiler

USE_GITHUB=	yes
GH_ACCOUNT=	hashicorp:DEFAULT,go_checkpoint,go_msgpack,go_multierror,go_syslog \
		hashicorp:golang_lru,hcl,logutils,memberlist,raft,raft_mdb,serf \
		hashicorp:scada,yamux,migrate,msgpackrpc,boltdb,reap,memdb \
		hashicorp:iradix,chttp,errwrap,gouuid,hil \
		armon:circbuf,go_metrics,go_radix,gomdb golang:protobuf,crypto,sys \
		boltdb:bolt inconshreveable:muxado matttproud:protobuf_ext \
		miekg:dns mitchellh:cli,mapstructure,copystructure,reflectwalk \
		prometheus:client_golang,client_model,procfs \
		ryanuber:columnize ugorji:go mattn:isatty \
		fsouza:dclient elazarl:assetfs bgentry:speakeasy DataDog:datadog
GH_PROJECT=	circbuf:circbuf protobuf:protobuf go-metrics:go_metrics \
		go-radix:go_radix gomdb:gomdb go-checkpoint:go_checkpoint \
		go-msgpack:go_msgpack go-multierror:go_multierror \
		go-syslog:go_syslog golang-lru:golang_lru hcl:hcl \
		logutils:logutils memberlist:memberlist raft:raft \
		raft-mdb:raft_mdb serf:serf scada-client:scada yamux:yamux \
		consul-migrate:migrate net-rpc-msgpackrpc:msgpackrpc \
		raft-boltdb:boltdb crypto:crypto bolt:bolt muxado:muxado \
		golang_protobuf_extensions:protobuf_ext dns:dns cli:cli \
		mapstructure:mapstructure client_golang:client_golang \
		client_model:client_model procfs:procfs columnize:columnize \
		go:go go-isatty:isatty go-reap:reap sys:sys go-memdb:memdb \
		go-immutable-radix:iradix go-cleanhttp:chttp errwrap:errwrap \
		go-dockerclient:dclient go-bindata-assetfs:assetfs \
		speakeasy:speakeasy datadog-go:datadog go-uuid:gouuid \
		hil:hil copystructure:copystructure reflectwalk:reflectwalk
GH_TAGNAME=	bbbad09:circbuf 2402d76:protobuf 345426c:go_metrics \
		4239b77:go_radix 151f2e0:gomdb e4b2dc3:go_checkpoint \
		fa3f638:go_msgpack d30f099:go_multierror 42a2b57:go_syslog \
		5c7531c:golang_lru 578dd97:hcl 0dc08b1:logutils \
		cef12ad:memberlist 057b893:raft 55f2947:raft_mdb e4ec8cc:serf \
		84989fd:scada df94978:yamux 678fb10:migrate \
		a14192a:msgpackrpc d1e82c1:boltdb 3760e01:crypto ee4a088:bolt \
		f693c7e:muxado d0c3fe8:protobuf_ext 75e6e86:dns cb6853d:cli \
		281073e:mapstructure 67994f1:client_golang \
		fa8ad6f:client_model 406e5b7:procfs 983d3a5:columnize \
		646ae4a:go 56b76bd:isatty 2d85522:reap 20457ee:sys 98f52f5:memdb \
		8e8ed81:iradix 875fb67:chttp 7554cd9:errwrap 9b6c972:dclient \
		57eb5e1:assetfs 36e9cfd:speakeasy b050cd8:datadog 3628998:gouuid \
		0457360:hil 6fc6626:copystructure eecf4c7:reflectwalk

USE_RC_SUBR=	consul

USERS=		consul
GROUPS=		consul

STRIP=		# stripping can break go binaries

post-patch:
	@${MKDIR} ${WRKSRC}/src/github.com/hashicorp/consul
.for src in .gitignore .travis.yml CHANGELOG.md GNUmakefile Godeps LICENSE \
	README.md acl api bench command commands.go consul contrib demo lib \
	main.go main_test.go make.bat scripts terraform test testutil tlsutil \
	ui vendor version.go watch website
	@${MV} ${WRKSRC}/${src} \
		${WRKSRC}/src/github.com/hashicorp/consul
.endfor
	@${MKDIR} ${WRKSRC}/src/github.com/armon
	@${MKDIR} ${WRKSRC}/src/github.com/boltdb
	@${MKDIR} ${WRKSRC}/src/github.com/inconshreveable
	@${MKDIR} ${WRKSRC}/src/github.com/miekg
	@${MKDIR} ${WRKSRC}/src/github.com/mitchellh
	@${MKDIR} ${WRKSRC}/src/github.com/ryanuber
	@${MKDIR} ${WRKSRC}/src/github.com/ugorji
	@${MKDIR} ${WRKSRC}/src/github.com/golang
	@${MKDIR} ${WRKSRC}/src/github.com/matttproud
	@${MKDIR} ${WRKSRC}/src/github.com/prometheus
	@${MKDIR} ${WRKSRC}/src/github.com/mattn
	@${MKDIR} ${WRKSRC}/src/github.com/fsouza
	@${MKDIR} ${WRKSRC}/src/github.com/elazarl
	@${MKDIR} ${WRKSRC}/src/github.com/bgentry
	@${MKDIR} ${WRKSRC}/src/github.com/DataDog
	@${MKDIR} ${WRKSRC}/src/golang.org/x
	@${MV} ${WRKSRC_circbuf} \
		${WRKSRC}/src/github.com/armon/circbuf
	@${MV} ${WRKSRC_go_metrics} \
		${WRKSRC}/src/github.com/armon/go-metrics
	@${MV} ${WRKSRC_go_radix} \
		${WRKSRC}/src/github.com/armon/go-radix
	@${MV} ${WRKSRC_gomdb} \
		${WRKSRC}/src/github.com/armon/gomdb
	@${MV} ${WRKSRC_protobuf} \
		${WRKSRC}/src/github.com/golang/protobuf
	@${MV} ${WRKSRC_go_msgpack} \
		${WRKSRC}/src/github.com/hashicorp/go-msgpack
	@${MV} ${WRKSRC_go_multierror} \
		${WRKSRC}/src/github.com/hashicorp/go-multierror
	@${MV} ${WRKSRC_go_checkpoint} \
		${WRKSRC}/src/github.com/hashicorp/go-checkpoint
	@${MV} ${WRKSRC_go_syslog} \
		${WRKSRC}/src/github.com/hashicorp/go-syslog
	@${MV} ${WRKSRC_golang_lru} \
		${WRKSRC}/src/github.com/hashicorp/golang-lru
	@${MV} ${WRKSRC_hcl} \
		${WRKSRC}/src/github.com/hashicorp/hcl
	@${MV} ${WRKSRC_logutils} \
		${WRKSRC}/src/github.com/hashicorp/logutils
	@${MV} ${WRKSRC_memberlist} \
		${WRKSRC}/src/github.com/hashicorp/memberlist
	@${MV} ${WRKSRC_raft} \
		${WRKSRC}/src/github.com/hashicorp/raft
	@${MV} ${WRKSRC_raft_mdb} \
		${WRKSRC}/src/github.com/hashicorp/raft-mdb
	@${MV} ${WRKSRC_serf} \
		${WRKSRC}/src/github.com/hashicorp/serf
	@${MV} ${WRKSRC_scada} \
		${WRKSRC}/src/github.com/hashicorp/scada-client
	@${MV} ${WRKSRC_yamux} \
		${WRKSRC}/src/github.com/hashicorp/yamux
	@${MV} ${WRKSRC_muxado} \
		${WRKSRC}/src/github.com/inconshreveable/muxado
	@${MV} ${WRKSRC_dns} \
		${WRKSRC}/src/github.com/miekg/dns
	@${MV} ${WRKSRC_cli} \
		${WRKSRC}/src/github.com/mitchellh/cli
	@${MV} ${WRKSRC_mapstructure} \
		${WRKSRC}/src/github.com/mitchellh/mapstructure
	@${MV} ${WRKSRC_columnize} \
		${WRKSRC}/src/github.com/ryanuber/columnize
	@${MV} ${WRKSRC_msgpackrpc} \
		${WRKSRC}/src/github.com/hashicorp/net-rpc-msgpackrpc
	@${MV} ${WRKSRC_protobuf_ext} \
		${WRKSRC}/src/github.com/matttproud/golang_protobuf_extensions
	@${MV} ${WRKSRC_client_golang} \
		${WRKSRC}/src/github.com/prometheus/client_golang
	@${MV} ${WRKSRC_client_model} \
		${WRKSRC}/src/github.com/prometheus/client_model
	@${MV} ${WRKSRC_procfs} \
		${WRKSRC}/src/github.com/prometheus/procfs
	@${MV} ${WRKSRC_boltdb} \
		${WRKSRC}/src/github.com/hashicorp/raft-boltdb
	@${MV} ${WRKSRC_bolt} \
		${WRKSRC}/src/github.com/boltdb/bolt
	@${MV} ${WRKSRC_migrate} \
		${WRKSRC}/src/github.com/hashicorp/consul-migrate
	@${MV} ${WRKSRC_isatty} \
		${WRKSRC}/src/github.com/mattn/go-isatty
	@${MV} ${WRKSRC_reap} \
		${WRKSRC}/src/github.com/hashicorp/go-reap
	@${MV} ${WRKSRC_memdb} \
		${WRKSRC}/src/github.com/hashicorp/go-memdb
	@${MV} ${WRKSRC_iradix} \
		${WRKSRC}/src/github.com/hashicorp/go-immutable-radix
	@${MV} ${WRKSRC_chttp} \
		${WRKSRC}/src/github.com/hashicorp/go-cleanhttp
	@${MV} ${WRKSRC_errwrap} \
		${WRKSRC}/src/github.com/hashicorp/errwrap
	@${MV} ${WRKSRC_dclient} \
		${WRKSRC}/src/github.com/fsouza/go-dockerclient
	@${MV} ${WRKSRC_assetfs} \
		${WRKSRC}/src/github.com/elazarl/go-bindata-assetfs
	@${MV} ${WRKSRC_speakeasy} \
		${WRKSRC}/src/github.com/bgentry/speakeasy
	@${MV} ${WRKSRC_datadog} \
		${WRKSRC}/src/github.com/DataDog/datadog-go
	@${MV} ${WRKSRC_sys} \
		${WRKSRC}/src/golang.org/x/sys
	@${MV} ${WRKSRC_crypto} \
		${WRKSRC}/src/golang.org/x/crypto
	@${MV} ${WRKSRC_gouuid} \
		${WRKSRC}/src/github.com/hashicorp/go-uuid
	@${MV} ${WRKSRC_hil} \
		${WRKSRC}/src/github.com/hashicorp/hil
	@${MV} ${WRKSRC_copystructure} \
		${WRKSRC}/src/github.com/mitchellh/copystructure
	@${MV} ${WRKSRC_reflectwalk} \
		${WRKSRC}/src/github.com/mitchellh/reflectwalk

do-build:
	@cd ${WRKSRC}/src/github.com/hashicorp/consul; ${SETENV} ${BUILD_ENV} GOPATH=${WRKSRC} go build \
		-ldflags "-X main.GitDescribe v${PORTVERSION}" -o bin/consul

do-install:
	${INSTALL_PROGRAM} ${WRKSRC}/src/github.com/hashicorp/consul/bin/consul ${STAGEDIR}${PREFIX}/bin/consul
	${MKDIR} ${STAGEDIR}${DATADIR}
	${MKDIR} ${WRKDIR}/dist
	${MV} ${WRKDIR}/index.html ${WRKDIR}/static ${WRKDIR}/dist
	cd ${WRKDIR}/dist && ${COPYTREE_SHARE} . ${STAGEDIR}${DATADIR}

.include <bsd.port.pre.mk>

# golang assumes that if clang is in use, it is called "clang" and not "cc". If
# it's called "cc", go fails.
.if ${COMPILER_TYPE} == clang
BUILD_ENV=	CC=clang
.endif

.include <bsd.port.post.mk>
