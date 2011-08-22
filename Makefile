# New ports collection makefile for:	spec
# Date created:		20 August 2011
# Whom:			Garrett Cooper <gcooper@FreeBSD.org>
#
# $FreeBSD
#

PORTNAME=	spec-sfs
PORTVERSION=	2008
CATEGORIES=	benchmarks

MAINTAINER=	gcooper@FreeBSD.org
COMMENT=	SPEC NFS and CIFS filesystem benchmark suite.

DISTFILES=

USE_GMAKE=
USE_JAVA=
USE_PERL5_RUN=	yes

JAVA_VERSION=	1.5

NO_PACKAGE=	license restricts redistribution
RESTRICTED=	license restricts redistribution

.include <bsd.port.pre.mk>

_mountpoint=
.for mountpoint in ${CD_MOUNTPTS}
.if exists(${mountpoint}/spec-sfs2008/COPYRIGHT)
_mountpoint=		${mountpoint}
.endif
.endfor
.if empty(_mountpoint)
IGNORE=		could not find the SPEC2008 media on ${CD_MOUNTPTS}
.endif

do-extract:
	@${RM} -rf ${WRKDIR}
	@${MKDIR} ${WRKSRC}
	(ktrace ${TAR} -cf - -C ${_mountpoint}/spec-sfs2008/ . && \
	 ${TOUCH} ${WRKSRC}/.fetch_done) | ${TAR} -xf - -C ${WRKSRC}
	@${TEST} -f ${WRKSRC}/.fetch_done

TEST_BINS=	bin/sfs_prime bin/sfs_syncd bin/sfscifs bin/sfsnfs3

TEST_DOC_DIRS=	html \
		html/SPECsfs2008_run_rules_files \
		html/SPECsfs2008_users_guide_files \
		ms-word \
		pdf \

TEST_DOCS=	html/SPECsfs2008_run_rules.htm \
		html/SPECsfs2008_run_rules_files/filelist.xml \
		html/SPECsfs2008_run_rules_files/header.htm \
		html/SPECsfs2008_run_rules_files/image001.wmz \
		html/SPECsfs2008_run_rules_files/image002.gif \
		html/SPECsfs2008_run_rules_files/image003.wmz \
		html/SPECsfs2008_run_rules_files/image004.gif \
		html/SPECsfs2008_run_rules_files/image005.wmz \
		html/SPECsfs2008_run_rules_files/image006.gif \
		html/SPECsfs2008_users_guide.htm \
		html/SPECsfs2008_users_guide_files/filelist.xml \
		html/SPECsfs2008_users_guide_files/header.htm \
		html/SPECsfs2008_users_guide_files/image001.gif \
		html/SPECsfs2008_users_guide_files/image002.gif \
		html/SPECsfs2008_users_guide_files/image003.gif \
		html/SPECsfs2008_users_guide_files/image004.gif \
		html/SPECsfs2008_users_guide_files/image005.gif \
		html/SPECsfs2008_users_guide_files/image006.gif \
		html/SPECsfs2008_users_guide_files/image007.gif \
		ms-word/SPECsfs2008_run_rules.doc \
		ms-word/SPECsfs2008_users_guide.doc \
		pdf/SPECsfs2008_run_rules.pdf \
		pdf/SPECsfs2008_users_guide.pdf \

PLIST_FILES=	${TEST_BINS} bin/UnivSystem.sh \
		share/examples/spec-sfs/sfs_ext_mon \

.for doc in ${TEST_DOCS}
PLIST_FILES+=	share/doc/spec-sfs/${doc}
.endfor

do-install:
	@${MKDIR} ${PREFIX}/bin
.for file in ${TEST_BINS}
	${STRIP_CMD} ${WRKSRC}/${file}
	${INSTALL_PROGRAM} ${WRKSRC}/${file} ${PREFIX}/${file}
.endfor
	${INSTALL_SCRIPT} ${WRKSRC}/src/UnivSystem.sh ${PREFIX}/bin
	@${MKDIR} ${PREFIX}/share/examples/spec-sfs
	${INSTALL_SCRIPT} ${WRKSRC}/bin/sfs_ext_mon \
	    ${PREFIX}/share/examples/spec-sfs
.for subdir in ${TEST_DOC_DIRS}
	${MKDIR} -m 00755 ${PREFIX}/share/doc/spec-sfs/${subdir}
.endfor
.for doc in ${TEST_DOCS}
	${INSTALL_DATA} ${WRKSRC}/documents/${doc} \
	    ${PREFIX}/share/doc/spec-sfs/${doc}
.endfor
.for subdir in ${TEST_DOC_DIRS}
	@${ECHO_CMD} "@unexec rmdir ${PREFIX}/share/doc/spec-sfs/${subdir}" >> \
	    ${TMPPLIST}
.endfor
.for dir in share/doc share/examples
	@${ECHO_CMD} "@unexec rmdir ${PREFIX}/${dir}/spec-sfs" >> ${TMPPLIST}
.endfor
.for dir in share/doc share/examples share
	@${ECHO_CMD} "@unexec rmdir ${PREFIX}/${dir} 2>/dev/null || true" >> \
	    ${TMPPLIST}
.endfor

post-install:
	@${ECHO_CMD}
	@${CAT} ${PKGMESSAGE}
	@${ECHO_CMD}

.include <bsd.port.post.mk>
