# $FreeBSD$

PORTNAME=	uefi-edk2-bhyve
PORTVERSION=	20160704
PORTREVISION=	1
CATEGORIES=	sysutils

MAINTAINER=	fabian.freyer@physik.tu-berlin.de
COMMENT?=	UEFI-EDK2 firmware for bhyve

LICENSE=	BSD2CLAUSE

BUILD_DEPENDS=	bash:shells/bash \
		nasm:devel/nasm \
		${PYTHON_LIBDIR}/lib-dynload/_sqlite3.so:databases/py27-sqlite3

USES=		gmake \
		python:2,build
USE_GCC=	4.8
USE_GITHUB=	yes
GH_ACCOUNT=	freebsd
GH_PROJECT=	uefi-edk2
GH_TAGNAME=	a36132939e259df79b16699c03c6f1d63c7454b9

PLIST_FILES=	${PREFIX}/share/uefi-firmware/BHYVE_UEFI${PLIST_SUFFIX}.fd

ONLY_FOR_ARCHS=	amd64

OPTIONS_DEFINE=	DEBUG

DEBUG_VARS=	uefi_target=DEBUG
DEBUG_VARS_OFF=	uefi_target=RELEASE

MAKE_ARGS+=	AS=${LOCALBASE}/bin/as \
		AR=${LOCALBASE}/bin/ar \
		LD=${LOCALBASE}/bin/ld \
		OBJCOPY=${LOCALBASE}/bin/objcopy \
		CC=${LOCALBASE}/bin/gcc48 \
		CXX=${LOCALBASE}/bin/g++48

BUILD_ARGS=-DDEBUG_ON_SERIAL_PORT=TRUE -D FD_SIZE_2MB

.include <bsd.port.options.mk>

.if defined(WITH_CSM)
PLIST_SUFFIX=	_CSM
BUILD_ARGS+=	-DCSM_ENABLE=TRUE
.endif

post-extract:
	@${REINPLACE_CMD} -e 's|python|${PYTHON_CMD}|' ${WRKSRC}/BaseTools/Tests/GNUmakefile \
							${WRKSRC}/BaseTools/BinWrappers/PosixLike/*

do-build:
	unset ARCH; unset MAKEFLAGS; ${MAKE_CMD} ${MAKE_ARGS} -C ${BUILD_WRKSRC}/BaseTools
	${MKDIR} ${BUILD_WRKSRC}/Build;
	${LN} -sf ${LOCALBASE}/bin/gcc48 ${BUILD_WRKSRC}/Build/gcc
	${LN} -sf ${LOCALBASE}/bin/ld ${BUILD_WRKSRC}/Build/ld
	${LN} -sf ${LOCALBASE}/bin/gmake ${BUILD_WRKSRC}/Build/make
	${LN} -sf ${LOCALBASE}/bin/ar ${BUILD_WRKSRC}/Build/ar
	${LN} -sf ${LOCALBASE}/bin/objcopy ${BUILD_WRKSRC}/Build/objcopy
	${LN} -sf ${LOCALBASE}/bin/nasm ${BUILD_WRKSRC}/Build/nasm
.if defined(WITH_CSM)
	bash -c " \
		cd ${BUILD_WRKSRC}; \
		source edksetup.sh;\
		unset ARCH; unset MAKEFLAGS; \
	        ${MAKE_CMD} ${MAKE_ARGS} GCC48_BIN=${BUILD_WRKSRC}/Build/ -C ${BUILD_WRKSRC}/BhyvePkg/Csm/BhyveCsm16/"
.endif
	bash -c " \
		cd ${BUILD_WRKSRC}; \
		source edksetup.sh;\
		unset ARCH; unset MAKEFLAGS; \
		export GCC48_BIN=${BUILD_WRKSRC}/Build/; \
		build -t GCC48 -a X64 -b ${UEFI_TARGET} -p BhyvePkg/BhyvePkgX64.dsc ${BUILD_ARGS} \
	"

do-install:
	${MKDIR} ${STAGEDIR}${PREFIX}/share/uefi-firmware/
	${INSTALL} ${BUILD_WRKSRC}/Build/BhyveX64/${UEFI_TARGET}_GCC48/FV/BHYVE.fd \
		${STAGEDIR}${PREFIX}/share/uefi-firmware/BHYVE_UEFI${PLIST_SUFFIX}.fd

.include <bsd.port.mk>
