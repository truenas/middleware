# $FreeBSD: $

PORTNAME=	riak-erlang
PORTVERSION=	16.b.02
PORTREVISION=	1
CATEGORIES=	lang
MASTER_SITES=	http://s3.amazonaws.com/downloads.basho.com/erlang/
DISTNAME=	otp_src_${ERL_RELEASE}
DIST_SUBDIR=	erlang

MAINTAINER=	nbari@dalmp.com
COMMENT=	Custom erlang from bashio to be used with riak2

WRKSRC=		${WRKDIR}/otp_src_${ERL_RELEASE}

ERLANG_LIB=	${PORTNAME}
ERL_RELEASE=	R16B02-basho5

USES=		gmake perl5
USE_GCC=	yes
USE_PERL5=	build
GNU_CONFIGURE=	yes
USE_OPENSSL=	yes

CONFIGURE_ARGS+=--with-ssl=/usr \
			--disable-hipe \
			--enable-smp-support \
			--enable-threads \
			--enable-kernel-poll \
			--enable-sctp

.include <bsd.port.mk>
