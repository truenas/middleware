# New ports collection makefile for:	spec
# Date created:		20 August 2011
# Whom:			Garrett Cooper <gcooper@FreeBSD.org>
#
# $FreeBSD
#

PORTNAME=	spec-sfs
PORTVERSION=	2008
CATEGORIES=	benchmarks
MASTER_SITES=
DISTFILES=

MAINTAINER=	gcooper@FreeBSD.org
COMMENT=	SPEC NFS and CIFS filesystem benchmark suite

RUN_DEPENDS=	p5-XML-XPath>=0:${PORTSDIR}/textproc/p5-XML-XPath

NO_PACKAGE=	license restricts redistribution
RESTRICTED=	license restricts redistribution

USE_GMAKE=
USE_JAVA=
USE_PERL5_RUN=	yes

JAVA_VERSION=	1.5

OPTIONS=	RESERVED_PORT	"Use privileged ports when doing NFS testing" on

.if defined(WITH_RESERVED_PORT)
CFLAGS+=	-DRESVPORT
.endif

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
	${RM} -rf ${WRKDIR}
	${MKDIR} ${WRKSRC}
	(${TAR} -cf - -C ${_mountpoint}/spec-sfs2008/ . && \
	 ${TOUCH} ${WRKSRC}/.fetch_done) | ${TAR} -xf - -C ${WRKSRC}
	${TEST} -f ${WRKSRC}/.fetch_done

MANAGER_JAR_DIRS=\
	manager \

MANAGER_JAR_FILES=\
	manager/Manager.jar \
	manager/SfsManager.jar \

SUBMIT_TOOLS_JAR_DIRS=\
	submit_tools/specreport/lib \
	submit_tools/specreport \
	submit_tools/subedit \
	submit_tools \

SUBMIT_TOOLS_JAR_FILES=\
	submit_tools/specreport/ChartGen.jar \
	submit_tools/specreport/lib/jcommon-1.0.0.jar \
	submit_tools/specreport/lib/jfreechart-1.0.1.jar \
	submit_tools/subedit/Subedit.jar \

SUBMIT_TOOLS_PERL_DIRS=\
	submit_tools/dev \
	submit_tools/lib \
	submit_tools \

SUBMIT_TOOLS_PERL_SCRIPTS=\
	submit_tools/dev/schema2table.pl \
	submit_tools/specreport.pl \
	submit_tools/subedit.pl \

SUBMIT_TOOLS_PERL_MODULES=\
	submit_tools/lib/Exceptions.pm \
	submit_tools/lib/HtmlParser.pm \
	submit_tools/lib/Html2Text.pm \
	submit_tools/lib/ReportRender.pm \
	submit_tools/lib/SimpleMath.pm \
	submit_tools/lib/SimpleObj.pm \

BINS=\
	bin/sfs_prime bin/sfs_syncd bin/sfscifs bin/sfsnfs3 \

DOC_DIRS=\
	html/SPECsfs2008_run_rules_files \
	html/SPECsfs2008_users_guide_files \
	html \
	ms-word \
	pdf \

DOCS=\
	html/SPECsfs2008_run_rules.htm \
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

PLIST_FILES=	${BINS} bin/UnivSystem.sh bin/specreport bin/subedit \
		%%EXAMPLESDIR%%/sfs_ext_mon \

USERS=		spec
GROUPS=		spec

.for doc in ${DOCS}
PLIST_FILES+=	%%DOCSDIR%%/${doc}
.endfor

.for file in ${MANAGER_JAR_FILES} ${SUBMIT_TOOLS_JAR_FILES}
PLIST_FILES+=	${PREFIX}/${PORTNAME}/${file}
.endfor

.for file in ${SUBMIT_TOOLS_PERL_MODULES}
PLIST_FILES+=	${PREFIX}/${PORTNAME}/${file}
.endfor

PLIST_FILES+=	${SUBMIT_TOOLS_PERL_SCRIPTS}

# XXX: why doesn't this work?
# PLIST_SUB+=	PORTNAME=${PORTNAME} SITE_PERL=${SITE_PERL}

SUB_FILES+=	pkg-message specreport subedit

generate-plist.2: generate-plist
	@${ECHO_CMD} "@unexec rmdir ${EXAMPLESDIR}" >> ${TMPPLIST}
.for dir in ${DOC_DIRS}
	@${ECHO_CMD} "@unexec rmdir ${DOCSDIR}/${dir}" >> ${TMPPLIST}
.endfor
	@${ECHO_CMD} "@unexec rmdir ${DOCSDIR}" >> ${TMPPLIST}
.for dir in ${MANAGER_JAR_DIRS}
	@${ECHO_CMD} "@unexec rmdir ${PREFIX}/${PORTNAME}/${dir}" >> \
	    ${TMPPLIST}
.endfor
.for dir in ${SUBMIT_TOOLS_JAR_DIRS}
	@${ECHO_CMD} "@unexec rmdir ${PREFIX}/${PORTNAME}/${dir}" >> \
	    ${TMPPLIST}
.endfor
	@${ECHO_CMD} "@unexec rmdir ${PREFIX}/${PORTNAME}" >> ${TMPPLIST}
.for dir in ${SUBMIT_TOOLS_PERL_DIRS}
	@${ECHO_CMD} "@unexec rmdir ${PREFIX}/${PORTNAME}/${dir}" >> \
	    ${TMPPLIST}
.endfor
	@${ECHO_CMD} "@unexec rmdir ${PREFIX}/${PORTNAME}" >> ${TMPPLIST}

do-install: generate-plist.2
	${MKDIR} ${PREFIX}/bin
.for file in ${BINS}
	${STRIP_CMD} ${WRKSRC}/${file}
	${INSTALL_PROGRAM} ${WRKSRC}/${file} ${PREFIX}/${file}
.endfor
.for file in specreport subedit
	# XXX: this sed hackery shouldn't be required.
	${REINPLACE_CMD} -e 's,%%PORTNAME%%,${PORTNAME},g' \
		-e 's,%%SITE_PERL%%,${SITE_PERL},g' ${WRKDIR}/${file}
	${INSTALL_SCRIPT} ${WRKDIR}/${file} ${PREFIX}/bin/${file:T}
.endfor
	${CHMOD} 04755 ${PREFIX}/bin/sfscifs
	${CHMOD} 04755 ${PREFIX}/bin/sfsnfs3
	${INSTALL_SCRIPT} ${WRKSRC}/src/UnivSystem.sh ${PREFIX}/bin
	${MKDIR} ${EXAMPLESDIR}
	${INSTALL_SCRIPT} ${WRKSRC}/bin/sfs_ext_mon ${EXAMPLESDIR}
.for dir in ${DOC_DIRS}
	${MKDIR} ${DOCSDIR}/${dir}
.endfor
.for doc in ${DOCS}
	${INSTALL_DATA} ${WRKSRC}/documents/${doc} ${DOCSDIR}/${doc}
.endfor
.for dir in ${MANAGER_JAR_DIRS}
	${MKDIR} ${PREFIX}/${PORTNAME}/${dir}
.endfor
.for file in ${MANAGER_JAR_FILES}
	${INSTALL_DATA} ${WRKSRC}/${file} ${PREFIX}/${PORTNAME}/${file}
.endfor
.for dir in ${SUBMIT_TOOLS_JAR_DIRS} 
	${MKDIR} ${PREFIX}/${PORTNAME}/${dir}
.endfor
.for file in ${SUBMIT_TOOLS_JAR_FILES}
	${INSTALL_DATA} ${WRKSRC}/${file} ${PREFIX}/${PORTNAME}/${file}
.endfor
.for dir in ${SUBMIT_TOOLS_PERL_DIRS}
	${MKDIR} ${PREFIX}/${PORTNAME}/${dir}
.endfor
.for file in ${SUBMIT_TOOLS_PERL_MODULES}
	${INSTALL_DATA} ${WRKSRC}/${file} ${PREFIX}/${PORTNAME}/${file}
.endfor
.for file in ${SUBMIT_TOOLS_PERL_SCRIPTS}
	${INSTALL_SCRIPT} ${WRKSRC}/${file} ${PREFIX}/${PORTNAME}/${file}
.endfor

post-install:
	@${ECHO_CMD}
	@${CAT} ${WRKDIR}/${PKGMESSAGE:T}
	@${ECHO_CMD}

.include <bsd.port.post.mk>
