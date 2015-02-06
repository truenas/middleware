.if exists(build/hooks/Makefile)
.include "build/hooks/Makefile"
.endif

NANO_LABEL?=FreeNAS
VERSION?=9.3-STABLE
TRAIN?=${NANO_LABEL}-9.3-STABLE
FREENAS_KEYFILE?=/dev/null
COMPANY?="iXsystems"
BUILD_TIMESTAMP!=date -u '+%Y%m%d%H%M'

STAGEDIR="${NANO_LABEL}-${VERSION}-${BUILD_TIMESTAMP}"
IX_INTERNAL_PATH="/freenas/Dev/releng/${NANO_LABEL}/jkh-nightlies/"
IX_STABLE_DIR="/freenas/Dev/releng/${NANO_LABEL}/9.3/STABLE/"

.ifdef SCRIPT
RELEASE_LOGFILE?=${SCRIPT}
.else
RELEASE_LOGFILE?=release.build.log
.endif


GIT_REPO_SETTING=.git-repo-setting
.if exists(${GIT_REPO_SETTING})
GIT_LOCATION!=cat ${GIT_REPO_SETTING}
.endif
ENV_SETUP=env NANO_LABEL=${NANO_LABEL} VERSION=${VERSION} GIT_LOCATION=${GIT_LOCATION} BUILD_TIMESTAMP=${BUILD_TIMESTAMP} SEQUENCE=${TRAIN}-${BUILD_TIMESTAMP}
ENV_SETUP+= TRAIN=${TRAIN}
ENV_SETUP+= UPDATE_USER=sef	# For now, just use sef's account
ENV_SETUP+= FREENAS_KEYFILE=${FREENAS_KEYFILE}
.if defined(CHANGELOG)
ENV_SETUP+= CHANGLOG=${CHANGELOG}
.endif

.if defined(NANO_ARCH)
 ENV_SETUP+= NANO_ARCH=${NANO_ARCH}
.endif

all:	build

.BEGIN:
	${ENV_SETUP} build/check_build_host.sh
.if !make(checkout) && !make(update) && !make(clean) && !make(distclean) && !make(git-internal) && !make(git-external)
	${ENV_SETUP} build/check_sandbox.sh
.endif

build: git-verify
	@[ `id -u` -eq 0 ] || ( echo "Sorry, you must be running as root to build this."; exit 1 )
	@${ENV_SETUP} ${MAKE} portsjail
	@${ENV_SETUP} ${MAKE} ports
	${ENV_SETUP} build/do_build.sh

checkout: git-verify
	${ENV_SETUP} build/do_checkout.sh

update: git-verify
	git pull
	${ENV_SETUP} build/do_checkout.sh

clean:
	${ENV_SETUP} build/build_cleanup.py
	rm -rf ${NANO_LABEL}-${VERSION}-* release.build.log
	rm -rf objs os-base

clean-packages:
	find objs/os-base/*/ports -type f -delete

clean-package:
.if defined(p)
	find objs/os-base/*/ports -name "${p}*" | xargs rm -fr
.else
	@echo "Clean a single package from object tree"
	@echo "" 
	@echo "Usage:  ${MAKE} ${.TARGET} p=[package name]"
	@echo ""
	@echo "Examples:"
	@echo "        ${MAKE} ${.TARGET} p=freenas-ui"
	@echo "        ${MAKE} ${.TARGET} p=netatalk"
.endif

clean-ui-package:
	${MAKE} clean-package p=freenas-ui

distclean: clean
	rm -fr FreeBSD nas_source

save-build-env:
	${ENV_SETUP} build/save_build.sh

freenas: release
release: git-verify
	@if [ "${NANO_LABEL}" = "TrueNAS" -a "${GIT_LOCATION}" != "INTERNAL" ]; then echo "You can only run this target from an internal repository."; exit 2; fi
	@echo "Doing executing target $@ on host: `hostname`"
	@echo "Build directory: `pwd`"
	${ENV_SETUP} script -a ${RELEASE_LOGFILE} ${MAKE} build
	${ENV_SETUP} script -a ${RELEASE_LOGFILE} build/create_release_distribution.sh
	${ENV_SETUP} script -a ${RELEASE_LOGFILE} build/create_upgrade_distribution.sh
	@if [ "${NANO_LABEL}" = "FreeNAS" ]; then echo "Building FreeNAS documentation"; (cd docs/userguide && make html && mv _build/html ../../objs/${STAGEDIR}/doc); fi

release-push: release
	${ENV_SETUP} /bin/sh build/post-to-upgrade.sh objs/LATEST/
	rm -rf "${IX_INTERNAL_PATH}/${STAGEDIR}"
	rm -rf "objs/${STAGEDIR}/FreeNAS-MANIFEST objs/${STAGEDIR}/Packages"
	cp ReleaseNotes UPGRADING ChangeLog "objs/${STAGEDIR}/"
	cp -r "objs/${STAGEDIR}" "${IX_INTERNAL_PATH}/${STAGEDIR}"
	if [ "${NANO_LABEL}" == "FreeNAS" ]; then \
		${ENV_SETUP} sh build/post-to-download.sh "${IX_INTERNAL_PATH}" "${NANO_LABEL}-${VERSION}" "${TRAIN}" "${BUILD_TIMESTAMP}"; \
		mv "${IX_INTERNAL_PATH}/${STAGEDIR}" "${IX_STABLE_DIR}"/`echo ${STAGEDIR} | awk -F- '{print $$4}'`; \
	fi
	${MAKE} save-build-env
	echo "Tell Matt to push his OCD button" | mail -s "Update ${BUILD_TIMESTAMP} now on download.freenas.org" web@ixsystems.com

update-push:	release
	${ENV_SETUP} /bin/sh build/post-to-upgrade.sh objs/LATEST/

archive:	release
.if !defined(ARCHIVE)
	@echo "ARCHIVE location must be defined" 1>&2
	false
.endif
.if !defined(RELEASEDB)
	@echo "RELEASEDB must be defined" 1>&2
	false
.endif
	/usr/local/bin/freenas-release -P ${NANO_LABEL} \
		-D ${RELEASEDB} --archive ${ARCHIVE} \
		-K ${FREENAS_KEYFILE} \
		add objs/LATEST

rebuild:
	@${ENV_SETUP} ${MAKE} checkout
	@${ENV_SETUP} ${MAKE} all
	@${ENV_SETUP) sh build/create_release_distribution.sh

cdrom:
	${ENV_SETUP} sh -x build/create_iso.sh

# intentionally split up to prevent abuse/spam
BUILD_BUG_DOMAIN?=ixsystems.com
BUILD_BUG_USER?=build-bugs
BUILD_BUG_EMAIL?=${BUILD_BUG_USER}@${BUILD_BUG_DOMAIN}

build-bug-report:
	mail -s "build fail for $${SUDO_USER:-$$USER}" ${BUILD_BUG_EMAIL} < \
		${RELEASE_LOGFILE}

git-verify:
	@if [ ! -f ${GIT_REPO_SETTING} ]; then \
		echo "No git repo choice is set.  Please use \"make git-external\" to build as an"; \
		echo "external developer or \"make git-internal\" to build as an ${COMPANY}"; \
		echo "internal developer.  You only need to do this once."; \
		exit 1; \
	fi
	@echo "NOTICE: You are building from the ${GIT_LOCATION} git repo."

git-internal:
	@echo "INTERNAL" > ${GIT_REPO_SETTING}
	@echo "You are set up for internal (${COMPANY}) development.  You can use"
	@echo "the standard make targets (e.g. build or release) now."

git-external:
	@echo "EXTERNAL" > ${GIT_REPO_SETTING}
	@echo "You are set up for external (github) development.  You can use"
	@echo "the standard make targets (e.g. build or release) now."

tag:
	${ENV_SETUP} build/apply_tag.sh

ports:
	@[ `id -u` -eq 0 ] || (echo "Sorry, you must be running as root to build this."; exit 1)
	${ENV_SETUP} build/ports/create-poudriere-conf.sh
	${ENV_SETUP} build/ports/create-poudriere-make.conf.sh
	${ENV_SETUP} build/ports/prepare-jail.sh
	${ENV_SETUP} build/ports/fetch-ports-srcs.sh
	${ENV_SETUP} build/ports/create-ports-list.sh
	${ENV_SETUP} build/ports/build-ports.sh

portsjail:
	${ENV_SETUP} build/build_jail.sh
