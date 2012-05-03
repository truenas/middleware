#
#    Makefile - Build example PBI's for FreeNAS
#

ARCH		!= uname -m

PBIPATH		?= /usr/pbi
PBIBUILDPATH	?= /usr/pbibuild
TOP		= ${PBIBUILDPATH}

.if ${ARCH} == "amd64"
PBIOUTPATH	?= ${PBIBUILDPATH}/pbiout64
.else
PBIOUTPATH	?= ${PBIBUILDPATH}/pbiout32
.endif


PBI_CREATE	!= which pbi_create
PBI_MAKEPORT	!= which pbi_makeport

.if empty(PBI_CREATE) || empty(PBI_MAKEPORT)
.error "pbi-manager is not installed"
.endif

transmission_port	= net-p2p/transmission-daemon
firefly_port		= audio/firefly
minidlna_port		= net/minidlna

TARGETS	= transmission firefly minidlna

.for t in ${TARGETS}
CLEAN_TARGETS += ${t}-clean
DISTCLEAN_TARGETS += ${t}-distclean
${t}_chroot = ${PBIPATH}/${t}-${ARCH}.chroot
.endfor

all: dirs ${TARGETS}
dirs:
	-mkdir -p ${PBIOUTPATH}

.for t in ${TARGETS}

${t}-clean:
.if exists(${${t}_chroot})
	-find ${${t}_chroot} | xargs chflags noschg
	-rm -rf ${${t}_chroot}
.endif

${t}-distclean:
	-rm -f ${PBIOUTPATH}/${t}*.pbi
	-rm -f ${PBIOUTPATH}/${t}*.sha256

${t}-build:
.if exists(${t}_pbi)
	${PBI_MAKEPORT} -c ${PBIOUTPATH}/${t}_pbi -o ${PBIOUTPATH} --tmpfs ${${t}_port}
.endif

${t}: ${t}-build
.endfor

clean: ${CLEAN_TARGETS}
distclean: ${DISTCLEAN_TARGETS}
